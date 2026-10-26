import datetime
import json
import os
from typing import Any, Dict, List, Optional
import structlog
from sqlmodel import Session, select

from receipt_api.models import ConstraintRecord, Outcome, ReceiptRecord

logger = structlog.get_logger(__name__)


def record_receipt_outcome(
    receipt_id: str,
    human_decision: str,  # merged | rejected | overridden
    note: Optional[str] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Record human/PR outcome and update institutional constraint confidence."""
    if session is None:
        from receipt_api.db import session_scope
        with session_scope() as s:
            return record_receipt_outcome(receipt_id, human_decision, note, session=s)

    # 1. Fetch receipt record
    receipt_rec = session.exec(
        select(ReceiptRecord).where(
            (ReceiptRecord.id == receipt_id) | (ReceiptRecord.public_slug == receipt_id)
        )
    ).first()

    if not receipt_rec:
        raise ValueError(f"Receipt '{receipt_id}' not found.")

    outcome_id = f"outc_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}_{os.urandom(3).hex()}"
    outcome = Outcome(
        id=outcome_id,
        receipt_id=receipt_rec.id,
        human_decision=human_decision.lower(),
        note=note,
    )
    session.add(outcome)

    # 2. Parse receipt JSON to identify affected constraints
    try:
        receipt_data = json.loads(receipt_rec.receipt_json)
    except Exception:
        receipt_data = {}

    constraints_checked = receipt_data.get("constraints", [])
    violated_ids = [
        c.get("id") or c.get("check_id")
        for c in constraints_checked
        if c.get("status") in ("VIOLATED", "FAIL")
    ]

    adjusted_constraints: List[Dict[str, Any]] = []

    # 3. Learning update logic
    for c_id in violated_ids:
        constraint = session.exec(
            select(ConstraintRecord).where(ConstraintRecord.id == c_id)
        ).first()
        if not constraint:
            continue

        prev_conf = constraint.confidence
        prev_prevented = constraint.prevented_count

        if human_decision == "rejected" or (human_decision == "merged" and receipt_data.get("repair_history")):
            # Constraint successfully caught a flaw that was rejected or repaired
            constraint.prevented_count += 1
            constraint.confidence = min(0.99, round(constraint.confidence + 0.05, 3))
            constraint.last_confirmed_at = datetime.datetime.now(datetime.timezone.utc)
            action = "reinforced"
        elif human_decision == "overridden":
            # Human ignored constraint violation (potential false positive)
            constraint.confidence = max(0.15, round(constraint.confidence - 0.15, 3))
            action = "penalized"
            if constraint.confidence < 0.35:
                constraint.status = "decayed"
                action = "decayed"
        else:
            action = "neutral"

        session.add(constraint)
        adjusted_constraints.append({
            "id": constraint.id,
            "action": action,
            "prev_confidence": prev_conf,
            "new_confidence": constraint.confidence,
            "prevented_count": constraint.prevented_count,
        })

    session.commit()
    logger.info("receipt_outcome_recorded", receipt_id=receipt_rec.id, decision=human_decision, adjustments=len(adjusted_constraints))

    return {
        "outcome_id": outcome_id,
        "receipt_id": receipt_rec.id,
        "decision": human_decision,
        "adjusted_constraints": adjusted_constraints,
    }


def get_learning_stats(repo_id: str, session: Session) -> Dict[str, Any]:
    """Retrieve learning loop summary metrics for repo dashboard."""
    constraints = session.exec(
        select(ConstraintRecord).where(ConstraintRecord.repo_id == repo_id)
    ).all()

    total_constraints = len(constraints)
    active_count = len([c for c in constraints if c.status == "active"])
    blocking_count = len([c for c in constraints if c.gate == "blocking" and c.status == "active"])
    proposed_count = len([c for c in constraints if c.status == "proposed"])
    decayed_count = len([c for c in constraints if c.status == "decayed"])
    total_prevented = sum(c.prevented_count for c in constraints)

    outcomes = session.exec(select(Outcome)).all()
    merged = len([o for o in outcomes if o.human_decision == "merged"])
    rejected = len([o for o in outcomes if o.human_decision == "rejected"])
    overridden = len([o for o in outcomes if o.human_decision == "overridden"])

    return {
        "repo_id": repo_id,
        "active_constraints": active_count,
        "blocking_constraints": blocking_count,
        "proposed_constraints": proposed_count,
        "decayed_constraints": decayed_count,
        "total_prevented_regressions": total_prevented,
        "outcomes": {
            "total": len(outcomes),
            "merged": merged,
            "rejected": rejected,
            "overridden": overridden,
        },
    }
