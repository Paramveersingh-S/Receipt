import structlog
from typing import List, Optional
from sqlmodel import Session

from receipt_api.scar.retrieve import search_constraints
from receipt_api.schemas import BriefingResponse, ConstraintSchema

logger = structlog.get_logger(__name__)


def generate_scar_briefing(
    repo_id: str,
    task: str,
    paths: List[str],
    session: Session,
    top_k: int = 4,
    token_budget: int = 1500,
) -> BriefingResponse:
    """Generate a compact pre-coding briefing for an agent with top constraints, checklist, and suggested tests."""
    search_query = f"{task} {' '.join(paths)}"
    primary_path = paths[0] if paths else None

    # Retrieve relevant constraints
    matched_constraints = search_constraints(
        repo_id=repo_id,
        query=search_query,
        session=session,
        path=primary_path,
        top_k=top_k,
    )

    # Build concise preflight checklist
    checklist: List[str] = []
    suggested_tests: List[str] = []

    for c in matched_constraints:
        checklist.append(f"[{c.severity.upper()}] {c.title}: {c.rule}")
        # Suggest verification test
        clean_name = c.id.replace("sc_", "").replace("-", "_")
        suggested_tests.append(f"test_{clean_name}_compliance")

    # If empty, add standard safeguards
    if not checklist:
        checklist = [
            "Ensure monetary operations use integer cents, never float arithmetic.",
            "Verify network mutations include deterministic idempotency keys.",
            "Check that all new API endpoints specify proper authentication dependencies.",
        ]
        suggested_tests = [
            "test_monetary_rounding_precision",
            "test_payment_idempotency_key",
        ]

    return BriefingResponse(
        constraints=matched_constraints,
        preflight_checklist=checklist[:5],
        suggested_tests=suggested_tests[:4],
    )


generate_briefing = generate_scar_briefing
