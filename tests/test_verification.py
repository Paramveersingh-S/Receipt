from pathlib import Path
import pytest
from sqlmodel import Session, select

from receipt_api.db import get_engine
from receipt_api.models import DBReceipt, DBRunEvent
from receipt_api.schemas import Receipt
from receipt_api.verify.failbefore import ProofItem
from receipt_api.verify.intent import AcceptanceCriterion, extract_intent, fallback_extract_intent
from receipt_api.verify.pipeline import VerificationPipeline
from receipt_api.verify.receipt import build_receipt, format_receipt_markdown
from receipt_api.verify.sandbox import SandboxConfig
from receipt_api.verify.scoring import calculate_score

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "repos"


def test_intent_extraction_classification():
    # Feature PR
    feat_criteria = fallback_extract_intent(
        title="feat: Add coupon discount support at checkout",
        body="- [ ] Coupon applies percentage discount to cart\n- [ ] Expired coupons return 400 Bad Request",
    )
    assert len(feat_criteria) == 2
    assert feat_criteria[0].kind == "feature"
    assert feat_criteria[0].testable is True
    assert "Coupon applies percentage" in feat_criteria[0].text

    # Bugfix PR
    fix_criteria = fallback_extract_intent(
        title="fix: Prevent double charging on payment retry timeout",
        body="Fixes Stripe retry race condition by passing idempotency key.",
    )
    assert len(fix_criteria) >= 1
    assert fix_criteria[0].kind == "bugfix"

    # Refactor PR
    refactor_criteria = fallback_extract_intent(
        title="refactor: Replace raw SQL queries with selectinload",
        body="Clean up database queries.",
    )
    assert len(refactor_criteria) >= 1
    assert refactor_criteria[0].kind == "refactor"


@pytest.mark.parametrize(
    "behavior,constraints,mutation,regression,has_reg,has_block,has_proof,is_bug,expected_verdict,max_score",
    [
        # Perfect run: all 1.0 -> 100, VERIFIED
        (1.0, 1.0, 1.0, 1.0, False, False, True, False, "VERIFIED", 100),
        # Typical verified PR (e.g. 0.89 mutation score) -> >=85, VERIFIED
        (1.0, 1.0, 0.89, 1.0, False, False, True, False, "VERIFIED", 100),
        # Hard Gate 1: Regressions detected -> Capped at REJECTED
        (1.0, 1.0, 1.0, 0.0, True, False, True, False, "REJECTED", 59),
        # Hard Gate 2: Blocking constraint violation -> Capped at NEEDS_REVIEW (<=69)
        (1.0, 0.0, 1.0, 1.0, False, True, True, False, "NEEDS_REVIEW", 69),
        # Hard Gate 3: Bugfix with 0 non-vacuous proofs -> Capped at NEEDS_REVIEW (<=69)
        (1.0, 1.0, 1.0, 1.0, False, False, False, True, "NEEDS_REVIEW", 69),
        # Poor behavior & test strength -> REJECTED
        (0.2, 0.5, 0.3, 0.8, False, False, True, False, "REJECTED", 59),
    ],
)
def test_scoring_formula_and_hard_gates(
    behavior,
    constraints,
    mutation,
    regression,
    has_reg,
    has_block,
    has_proof,
    is_bug,
    expected_verdict,
    max_score,
):
    res = calculate_score(
        behavior=behavior,
        constraints=constraints,
        test_strength=mutation,
        regression=regression,
        has_regressions=has_reg,
        has_blocking_violations=has_block,
        has_non_vacuous_proofs=has_proof,
        is_bugfix=is_bug,
    )
    assert res.verdict == expected_verdict
    assert res.score <= max_score
    if has_reg or has_block or (is_bug and not has_proof):
        assert res.hard_gate_triggered is not None


def test_receipt_builder_and_markdown():
    receipt = build_receipt(
        repo_name="acme/receipt-demo-shop",
        pr_number=12,
        pr_title="Add coupon discount support",
        pr_author="agent/claude-code",
        base_sha="a1b2c3d4e5f6",
        head_sha="d4e5f6a1b2c3",
        verdict="VERIFIED",
        score=92,
        duration_ms=45200,
        intent=[{"id": "ac1", "text": "Coupon applies percentage", "testable": True, "kind": "feature"}],
        proofs=[
            {
                "criterion_id": "ac1",
                "test_name": "test_coupon_rounds_half_up",
                "base": "FAIL",
                "head": "PASS",
                "vacuous": False,
            }
        ],
        suite={"base": {"passed": 40, "failed": 0}, "head": {"passed": 42, "failed": 0}, "regressions": []},
        mutation={"mutants": 20, "killed": 18, "survived": 2, "timeout": 0, "score": 0.9, "survivors": []},
        constraints=[
            {
                "constraint_id": "sc_001",
                "title": "Money is integer cents",
                "severity": "block",
                "result": "PASS",
                "evidence": [],
            }
        ],
        browser={"applicable": False, "checks": []},
        score_breakdown={"behavior": 1.0, "constraints": 1.0, "test_strength": 0.9, "regression": 1.0},
        limits=["Test ran in restricted subprocess mode"],
    )

    assert isinstance(receipt, Receipt)
    assert receipt.verdict == "VERIFIED"
    assert receipt.score == 92
    assert len(receipt.slug) == 6

    md = format_receipt_markdown(receipt)
    assert "RECEIPT: [VERIFIED]" in md
    assert "acme/receipt-demo-shop" in md
    assert "test_coupon_rounds_half_up" in md
    assert "90%" in md  # Mutation score 0.9 * 100


def test_verification_pipeline_py_calc(test_db_isolation):
    py_repo = FIXTURES_DIR / "py_calc"
    pipeline = VerificationPipeline(
        repo_path=py_repo,
        repo_name="acme/py-calc",
        pr_number=1,
        pr_title="feat: Add multiply function",
        pr_body="- [ ] Multiply two integers correctly",
        pr_author="agent/claude-code",
        config=SandboxConfig(timeout_seconds=15),
    )

    with Session(get_engine()) as session:
        receipt = pipeline.run(session=session)

        assert isinstance(receipt, Receipt)
        assert receipt.verdict in ("VERIFIED", "NEEDS_REVIEW")
        assert receipt.pr.number == 1
        assert receipt.repo == "acme/py-calc"

        # Check that receipt was recorded in database
        db_receipt = session.exec(select(DBReceipt).where(DBReceipt.id == receipt.id)).first()
        assert db_receipt is not None
        assert db_receipt.verdict == receipt.verdict

        # Check that SSE events were emitted and persisted
        events = session.exec(select(DBRunEvent).where(DBRunEvent.run_id == pipeline.run_id)).all()
        assert len(events) >= 3
        event_types = [e.type for e in events]
        assert "run.started" in event_types
        assert "run.finished" in event_types
