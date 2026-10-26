import json
from pathlib import Path
import pytest
from receipt_api.schemas import ConstraintSchema, ReceiptSchema

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT_DIR / "contracts" / "fixtures"
CONTRACTS_DIR = ROOT_DIR / "contracts"


def test_receipt_verified_fixture_validates():
    path = FIXTURES_DIR / "receipt.verified.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    receipt = ReceiptSchema.model_validate(data)
    assert receipt.verdict == "VERIFIED"
    assert receipt.score >= 85
    assert len(receipt.proofs) > 0
    assert any(p.base == "FAIL" and p.head == "PASS" and not p.vacuous for p in receipt.proofs)


def test_receipt_rejected_fixture_validates():
    path = FIXTURES_DIR / "receipt.rejected.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    receipt = ReceiptSchema.model_validate(data)
    assert receipt.verdict == "REJECTED"
    assert receipt.score < 60
    assert len(receipt.suite.regressions) > 0


def test_receipt_needs_review_fixture_validates():
    path = FIXTURES_DIR / "receipt.needs_review.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    receipt = ReceiptSchema.model_validate(data)
    assert receipt.verdict == "NEEDS_REVIEW"
    assert 60 <= receipt.score <= 84


def test_constraints_list_fixture():
    path = FIXTURES_DIR / "constraints.list.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 14, f"Expected at least 14 constraints, found {len(data)}"
    for item in data:
        c = ConstraintSchema.model_validate(item)
        assert c.id.startswith("sc_")
        assert len(c.evidence) > 0, f"Constraint {c.id} missing evidence"


def test_constraint_detail_fixture():
    path = FIXTURES_DIR / "constraint.detail.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    c = ConstraintSchema.model_validate(data)
    assert c.id == "sc_001"
    assert c.severity == "block"


def test_events_ndjson_fixtures_structure():
    schema_path = CONTRACTS_DIR / "events.schema.json"
    assert schema_path.exists()
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    allowed_types = set(schema["properties"]["type"]["enum"])

    for filename in ("ingest.events.ndjson", "run.events.verified.ndjson", "run.events.repair.ndjson"):
        path = FIXTURES_DIR / filename
        assert path.exists(), f"Missing fixture {filename}"
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            assert len(lines) > 0
            for line in lines:
                ev = json.loads(line)
                assert "seq" in ev
                assert "type" in ev
                assert "at" in ev
                assert "payload" in ev
                assert ev["type"] in allowed_types, f"Unknown event type: {ev['type']} in {filename}"


def test_openapi_contains_all_b6_endpoints():
    openapi_path = CONTRACTS_DIR / "openapi.json"
    assert openapi_path.exists()
    with open(openapi_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    paths = spec.get("paths", {})
    required_paths = [
        "/repos",
        "/repos/{id}",
        "/repos/{id}/ingest",
        "/repos/{id}/constraints",
        "/constraints/{id}",
        "/constraints/{id}/feedback",
        "/repos/{id}/briefing",
        "/repos/{id}/check-diff",
        "/repos/{id}/runs",
        "/runs/{id}",
        "/receipts/{id}",
        "/r/{slug}",
        "/receipts/{id}/markdown",
        "/repos/{id}/docs",
        "/repos/{id}/docs/sync",
        "/repos/{id}/graph",
        "/repos/{id}/stats",
        "/bench/results",
        "/webhooks/github",
        "/artifacts/{id}",
        "/health",
    ]
    for p in required_paths:
        assert p in paths, f"Missing required path in openapi.json: {p}"
