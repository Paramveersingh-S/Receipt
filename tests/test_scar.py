import json
import pytest
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine, select

from receipt_api.github.ingest import ingest_from_snapshot
from receipt_api.models import GHEvent, Constraint, ConstraintEvidence
from receipt_api.scar.checks import (
    run_static_checks_on_code,
    run_static_checks_on_diff,
)
from receipt_api.scar.extract import extract_constraints_from_repo_events
from receipt_api.scar.retrieve import search_constraints
from receipt_api.scar.score import calculate_constraint_confidence
from receipt_api.scar.store import get_constraint, list_constraints, save_constraint
from receipt_api.schemas import EvidenceItem


@pytest.fixture
def scar_db_session(tmp_path):
    db_file = tmp_path / "test_scar.db"
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
    with Session(engine) as session:
        yield session


def test_static_checks_all_patterns():
    # 1. Float math on money
    code_float = """
def calculate_discount(price_cents, discount_pct):
    return price_cents * 0.15
"""
    v_float = run_static_checks_on_code(code_float)
    assert any(v.check_id == "float-arithmetic-on-money" for v in v_float)

    # 2. Bare exception in payment logic
    code_except = """
def process_payment(amount_cents):
    try:
        gateway.charge(amount_cents)
    except Exception:
        pass
"""
    v_except = run_static_checks_on_code(code_except)
    assert any(v.check_id == "bare-exception" for v in v_except)

    # 3. Missing idempotency key
    code_idemp = """
def charge_customer(order_id, amount):
    gateway.charge(order_id=order_id, amount=amount)
"""
    v_idemp = run_static_checks_on_code(code_idemp)
    assert any(v.check_id == "missing-idempotency-key" for v in v_idemp)

    # 4. N+1 query loop
    code_n1 = """
def list_items(items, session):
    for item in items:
        session.exec(select(Review).where(Review.item_id == item.id))
"""
    v_n1 = run_static_checks_on_code(code_n1)
    assert any(v.check_id == "n-plus-one-query" for v in v_n1)

    # 5. Missing auth dependency
    code_auth = """
@app.post("/admin/settings")
def update_settings(payload: dict):
    return {"status": "ok"}
"""
    v_auth = run_static_checks_on_code(code_auth)
    assert any(v.check_id == "missing-auth-dependency" for v in v_auth)

    # 6. PII logging
    code_pii = """
def handle_checkout(payload):
    logger.info("Processing checkout", card_number=payload['card_number'])
"""
    v_pii = run_static_checks_on_code(code_pii)
    assert any(v.check_id == "pii-logging" for v in v_pii)

    # 7. Non-reversible migration
    code_mig = """
def upgrade():
    op.add_column("orders", "coupon_id")

def downgrade():
    pass
"""
    v_mig = run_static_checks_on_code(code_mig)
    assert any(v.check_id == "non-reversible-migration" for v in v_mig)


def test_static_checks_on_diff():
    diff_sample = """--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -40,3 +40,3 @@
-    return int(round(total * discount_pct))
+    return price_cents * 0.15
"""
    violations = run_static_checks_on_diff(diff_sample)
    assert len(violations) > 0
    assert any(v.check_id == "float-arithmetic-on-money" for v in violations)


def test_confidence_scoring():
    # Incident fix evidence
    ev_incident = [
        EvidenceItem(
            type="incident_fix",
            url="https://github.com/test/repo/issues/10",
            excerpt="Double charge incident fix",
            at="2026-10-01T00:00:00Z",
        )
    ]
    conf_incident = calculate_constraint_confidence(ev_incident)
    assert conf_incident >= 0.85

    # Multiple corroborating sources boost confidence
    ev_multi = [
        EvidenceItem(type="revert", url="https://github.com/test/repo/pull/4", excerpt="Revert N+1"),
        EvidenceItem(type="review", url="https://github.com/test/repo/pull/3#r1", excerpt="Loop query"),
    ]
    conf_multi = calculate_constraint_confidence(ev_multi)
    assert conf_multi >= 0.80


def test_scar_extraction_and_provenance(scar_db_session):
    repo_id = "repo_demo_shop"
    snapshot_path = Path("demo/seed/snapshot.json")
    assert snapshot_path.exists()

    # 1. Ingest events
    ingest_from_snapshot(repo_id, snapshot_path, scar_db_session)
    scar_db_session.commit()

    all_events = scar_db_session.exec(select(GHEvent).where(GHEvent.repo_id == repo_id)).all()
    assert len(all_events) > 0
    event_urls = {e.url for e in all_events}

    # 2. Extract constraints
    extracted = extract_constraints_from_repo_events(repo_id, scar_db_session)
    assert len(extracted) >= 6, f"Expected >=6 extracted constraints, got {len(extracted)}"

    # 3. Prove 100% evidence links resolve to real ingested GHEvent rows
    for c in extracted:
        assert len(c.evidence) > 0
        for ev in c.evidence:
            assert ev.url in event_urls, f"Evidence URL {ev.url} not found in ingested events!"

    # 4. Check against planted lessons
    planted_path = Path("demo/seed/planted_lessons.json")
    with open(planted_path, "r", encoding="utf-8") as f:
        planted = json.load(f)

    recovered_count = 0
    for p in planted:
        # Match by pattern or title keyword
        matched = False
        for c in extracted:
            if any(term in c.title.lower() for term in p["title"].lower().split()[:3]):
                matched = True
                break
        if matched:
            recovered_count += 1

    print(f"Planted lesson recall: {recovered_count}/{len(planted)} ({recovered_count/len(planted)*100:.1f}%)")
    assert recovered_count >= 6, f"Expected >=6 of 7 planted lessons recovered, got {recovered_count}"


def test_hybrid_retrieval(scar_db_session):
    repo_id = "repo_demo_shop"
    snapshot_path = Path("demo/seed/snapshot.json")
    ingest_from_snapshot(repo_id, snapshot_path, scar_db_session)
    extract_constraints_from_repo_events(repo_id, scar_db_session)

    # Search for "retry payment"
    results = search_constraints(
        repo_id=repo_id,
        query="retry payment idempotency",
        session=scar_db_session,
        top_k=3,
    )

    assert len(results) > 0
    top_titles = [c.title.lower() for c in results]
    assert any("idempotency" in t or "payment" in t for t in top_titles), f"Top results: {top_titles}"
