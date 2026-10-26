import json
from pathlib import Path
import pytest
from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient

from receipt_api.main import app
from receipt_api.github.ingest import ingest_from_snapshot
from receipt_api.scar.briefing import generate_scar_briefing
from receipt_api.scar.extract import extract_constraints_from_repo_events
from receipt_api.verify.pipeline import VerificationPipeline
from receipt_api.verify.sandbox import SandboxConfig


@pytest.fixture
def fusion_db(tmp_path):
    db_file = tmp_path / "fusion.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS constraints_fts USING fts5(
                    id UNINDEXED,
                    title,
                    rule,
                    why
                );
                """
            )
        )
        conn.commit()

    repo_id = "repo_demo_shop"
    snapshot_path = Path("demo/seed/snapshot.json")

    with Session(engine) as session:
        ingest_from_snapshot(repo_id, snapshot_path, session)
        extract_constraints_from_repo_events(repo_id, session)

    with Session(engine) as session:
        yield session, repo_id


def test_briefing_generation(fusion_db):
    session, repo_id = fusion_db
    briefing = generate_scar_briefing(
        repo_id=repo_id,
        task="add coupon support and discount calculation at checkout",
        paths=["shop/pricing.py", "shop/checkout.py"],
        session=session,
        top_k=4,
    )

    assert len(briefing.constraints) > 0
    assert len(briefing.preflight_checklist) > 0
    assert len(briefing.suggested_tests) > 0

    # Ensure money integer cents or idempotency is present in briefing
    titles = [c.title.lower() for c in briefing.constraints]
    assert any("cents" in t or "float" in t or "idempotency" in t for t in titles)


def test_briefing_api_endpoint():
    client = TestClient(app)
    res = client.post(
        "/repos/repo_demo_shop/briefing",
        json={
            "task": "add coupon support at checkout",
            "paths": ["shop/pricing.py", "shop/checkout.py"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "constraints" in data
    assert "preflight_checklist" in data
    assert "suggested_tests" in data
    assert len(data["constraints"]) > 0


def test_verification_fusion_subtle_vs_correct(tmp_path):
    # Setup test workspace
    repo_dir = tmp_path / "calc_test"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n', encoding="utf-8")
    
    # 1. Subtle bug file
    subtle_file = repo_dir / "pricing.py"
    subtle_file.write_text(
        "def compute_discount(price_cents, discount_pct):\n"
        "    return price_cents * 0.15\n"
        "def charge_user(order_id, amount):\n"
        "    return gateway.charge(order_id=order_id, amount=amount)\n",
        encoding="utf-8",
    )
    test_file = repo_dir / "test_pricing.py"
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

    pipeline_subtle = VerificationPipeline(
        repo_path=repo_dir,
        repo_name="demo/shop",
        pr_number=12,
        pr_title="Add coupon support",
        pr_body="Adds discount calculation with percentage discount",
    )
    receipt_subtle = pipeline_subtle.run()

    # Subtle bug must fail constraints and be capped
    failed_c = [c for c in receipt_subtle.constraints if c.result == "FAIL"]
    assert len(failed_c) > 0
    assert receipt_subtle.verdict in ("NEEDS_REVIEW", "REJECTED")
    assert receipt_subtle.score <= 69

    # 2. Correct implementation
    subtle_file.write_text(
        "def compute_discount(price_cents, discount_pct):\n"
        "    return (price_cents * discount_pct + 50) // 100\n"
        "def charge_user(order_id, amount, idempotency_key):\n"
        "    return gateway.charge(order_id=order_id, amount=amount, idempotency_key=idempotency_key)\n",
        encoding="utf-8",
    )

    pipeline_correct = VerificationPipeline(
        repo_path=repo_dir,
        repo_name="demo/shop",
        pr_number=13,
        pr_title="Add correct coupon support",
        pr_body="Adds integer cents discount calculation",
    )
    receipt_correct = pipeline_correct.run()

    # Correct must have 0 constraint failures
    failed_correct = [c for c in receipt_correct.constraints if c.result == "FAIL"]
    assert len(failed_correct) == 0
    assert getattr(receipt_correct.score_breakdown, "constraints", 1.0) == 1.0
