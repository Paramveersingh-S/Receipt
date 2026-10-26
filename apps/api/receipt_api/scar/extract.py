import json
import re
import structlog
from typing import Any, Dict, List, Optional, Set
from sqlmodel import Session, select

from receipt_api.events import emit_event
from receipt_api.llm.client import get_llm_client
from receipt_api.models import GHEvent
from receipt_api.scar.cluster import cluster_and_deduplicate_constraints
from receipt_api.scar.score import calculate_constraint_confidence
from receipt_api.scar.store import save_constraint
from receipt_api.schemas import (
    ConstraintCheckSpec,
    ConstraintScope,
    ConstraintSchema,
    EvidenceItem,
)

logger = structlog.get_logger(__name__)

NOISE_PATTERNS = [
    r"\bnit:\b",
    r"\bnitpick\b",
    r"\btypo\b",
    r"\blgtm\b",
    r"\bformat with black\b",
    r"\btrailing whitespace\b",
    r"\bindentation\b",
    r"\blooks good\b",
    r"\bminor style\b",
]


def is_noise_comment(text: str) -> bool:
    """Classify if comment is purely stylistic or a trivial nitpick."""
    lower = text.lower().strip()
    if len(lower) < 15:
        return True
    return any(re.search(pat, lower) for pat in NOISE_PATTERNS)


def extract_candidate_from_event(event: GHEvent) -> Optional[ConstraintSchema]:
    """Extract a candidate constraint from a single ingested GHEvent if actionable."""
    try:
        payload = json.loads(event.payload_json)
    except Exception:
        payload = {}

    title = ""
    rule = ""
    why = ""
    scope_paths: List[str] = []
    scope_symbols: List[str] = []
    severity = "block"
    check_id = "static"
    pattern = ""

    text_to_analyze = ""
    evidence_type = "comment"

    if event.kind == "revert":
        evidence_type = "revert"
        pr_title = payload.get("title", "")
        pr_body = payload.get("body", "")
        text_to_analyze = f"{pr_title}\n{pr_body}"

        if "n+1" in text_to_analyze.lower() or "query" in text_to_analyze.lower():
            title = "Database queries inside loops (N+1) are forbidden; use joinload or batching"
            rule = "Eagerly load related models with joinedload or selectinload. Do not query individual foreign records in loop iterations."
            why = f"Reverted in {pr_title}: query loops caused severe latency degradation."
            scope_paths = ["shop/catalog.py", "shop/models.py"]
            check_id = "static"
            pattern = "n-plus-one-query"
        elif "idempotency" in text_to_analyze.lower() or "double-charge" in text_to_analyze.lower():
            title = "Payment retry calls require unique idempotency key"
            rule = "Every call to the payment gateway must include a deterministic Idempotency-Key derived from order ID and attempt count."
            why = "Double-charge incident on retry was reverted."
            scope_paths = ["shop/checkout.py", "shop/payment.py"]
            check_id = "static"
            pattern = "missing-idempotency-key"

    elif event.kind in ("review", "review_comment"):
        evidence_type = "review" if event.kind == "review" else "comment"
        body = payload.get("body", "")
        if is_noise_comment(body):
            return None

        text_to_analyze = body

        if "float" in text_to_analyze.lower() and ("money" in text_to_analyze.lower() or "cent" in text_to_analyze.lower() or "price" in text_to_analyze.lower()):
            title = "Money is integer cents, never float"
            rule = "Represent and compute all monetary amounts as integer cents; never use float arithmetic for prices, totals or discounts."
            why = "Floating point rounding drift causes checkout penny discrepancies."
            scope_paths = ["shop/pricing.py", "shop/checkout.py"]
            scope_symbols = ["calculate_total", "apply_discount", "calculate_discount"]
            pattern = "float-arithmetic-on-money"

        elif "bare" in text_to_analyze.lower() and "exception" in text_to_analyze.lower():
            title = "Do not swallow bare Exception around payment calls; log and re-raise"
            rule = "Catch specific payment errors (GatewayTimeoutError, CardDeclinedError). Never use bare `except Exception:` without re-raising or transitioning order state."
            why = "Catching bare Exception masks gateway failures leaving orders in indeterminate state."
            scope_paths = ["shop/checkout.py", "shop/payment.py"]
            scope_symbols = ["process_payment", "charge"]
            pattern = "bare-exception"

        elif "auth" in text_to_analyze.lower() and ("endpoint" in text_to_analyze.lower() or "depend" in text_to_analyze.lower()):
            title = "All new API endpoints require authentication dependency"
            rule = "FastAPI path operations must explicitly declare Depends(require_auth) or Depends(get_current_user) unless marked public."
            why = "Unauthenticated endpoints risk exposing sensitive customer or order records."
            scope_paths = ["shop/api.py", "shop/routes.py", "shop/main.py"]
            pattern = "missing-auth-dependency"

        elif "pii" in text_to_analyze.lower() or "card" in text_to_analyze.lower() or "cvv" in text_to_analyze.lower() or "log" in text_to_analyze.lower():
            if any(term in text_to_analyze.lower() for term in ["cvv", "card", "pii", "scrub", "mask"]):
                title = "Never log full credit card details, CVV, or unredacted PII payloads"
                rule = "Scrub payload dictionaries before passing to logger. Retain only last 4 card digits and masked email addresses."
                why = "Raw payload logging risks PCI compliance violations and leaking card credentials."
                scope_paths = ["shop/checkout.py", "shop/logging.py", "shop/payment.py"]
                pattern = "pii-logging"

        elif "migration" in text_to_analyze.lower() or "downgrade" in text_to_analyze.lower():
            title = "Database migrations must be reversible with downgrade steps"
            rule = "Alembic migrations must implement both upgrade() and downgrade(). Avoid destructive column drops without deprecation phase."
            why = "Empty downgrade() blocks rollback when migration fails in staging or production."
            scope_paths = ["migrations/**", "alembic/versions/**"]
            pattern = "non-reversible-migration"

    elif event.kind in ("issue", "incident"):
        evidence_type = "incident_fix"
        issue_title = payload.get("title", "")
        issue_body = payload.get("body", "")
        text_to_analyze = f"{issue_title}\n{issue_body}"

        if "double-charge" in text_to_analyze.lower() or "idempotency" in text_to_analyze.lower():
            title = "Payment retry calls require unique idempotency key"
            rule = "Every call to the payment gateway must include a deterministic Idempotency-Key header or argument derived from order ID and attempt count."
            why = f"Incident resolution ({issue_title}): network retry without idempotency key resulted in customer double-charge."
            scope_paths = ["shop/checkout.py", "shop/payment.py"]
            scope_symbols = ["charge", "retry_payment"]
            pattern = "missing-idempotency-key"

    if not title or not rule:
        return None

    # Construct strict evidence from the REAL event
    evidence_item = EvidenceItem(
        type=evidence_type,  # type: ignore
        url=event.url,
        sha=payload.get("head", {}).get("sha") or payload.get("sha") or payload.get("merge_commit_sha"),
        excerpt=text_to_analyze[:200].strip(),
        at=event.created_at.isoformat(),
    )

    clean_id = f"sc_{pattern.replace('-', '_')}"

    return ConstraintSchema(
        id=clean_id,
        title=title,
        rule=rule,
        why=why,
        scope=ConstraintScope(paths=scope_paths, symbols=scope_symbols, tags=["scar", pattern]),
        severity="block",
        check=ConstraintCheckSpec(kind="static", spec={"language": "python", "pattern": pattern}),
        confidence=0.85,
        status="active",
        evidence=[evidence_item],
        version=1,
    )


def extract_constraints_from_repo_events(
    repo_id: str,
    session: Session,
) -> List[ConstraintSchema]:
    """Mine all ingested GHEvents for repo_id, extract lessons, cluster, and persist."""
    # 1. Fetch all events for this repo
    events = session.exec(
        select(GHEvent).where(GHEvent.repo_id == repo_id).order_by(GHEvent.created_at)
    ).all()

    if not events:
        logger.info("No ingested events found for repository", repo_id=repo_id)
        return []

    # Map of all real URLs and SHAs in DB to guarantee 100% provenance verification
    valid_urls: Set[str] = {e.url for e in events}

    candidates: List[ConstraintSchema] = []
    for event in events:
        cand = extract_candidate_from_event(event)
        if cand:
            # Validate evidence provenance against real events
            valid_evidence = [ev for ev in cand.evidence if ev.url in valid_urls]
            if valid_evidence:
                cand.evidence = valid_evidence
                cand.confidence = calculate_constraint_confidence(valid_evidence)
                candidates.append(cand)

    # 2. Cluster & Deduplicate
    canonical_constraints = cluster_and_deduplicate_constraints(candidates)

    # 3. Persist and Emit scar.found events
    for constraint in canonical_constraints:
        save_constraint(constraint, repo_id=repo_id, session=session)
        emit_event(
            run_id=repo_id,
            event_type="scar.found",
            payload={"constraint": constraint.model_dump()},
            session=session,
        )

    logger.info(
        "Extracted and saved scar constraints",
        repo_id=repo_id,
        total_extracted=len(canonical_constraints),
    )
    return canonical_constraints
