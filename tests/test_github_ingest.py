import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from receipt_api.db import get_engine
from receipt_api.github.ingest import ingest_from_snapshot
from receipt_api.github.webhooks import handle_webhook_event, verify_github_signature
from receipt_api.main import app
from receipt_api.models import DBRun, DBRunEvent, GHEvent

SNAPSHOT_PATH = Path(__file__).parent.parent / "demo" / "seed" / "snapshot.json"


def test_ingest_from_snapshot_idempotent(test_db_isolation):
    repo_id = "repo_test_ingest"

    with Session(get_engine()) as session:
        # First ingestion run
        stats_1 = ingest_from_snapshot(repo_id, SNAPSHOT_PATH, session)
        assert stats_1["total_new"] > 0
        assert stats_1["prs"] > 0
        assert stats_1["comments"] > 0
        assert stats_1["reverts"] >= 1
        assert stats_1["duplicates_skipped"] == 0

        # Query database directly to confirm events stored
        events = session.exec(select(GHEvent).where(GHEvent.repo_id == repo_id)).all()
        assert len(events) == stats_1["total_new"]

        kinds = {e.kind for e in events}
        assert "pr" in kinds
        assert "review" in kinds
        assert "review_comment" in kinds
        assert "revert" in kinds

        # Second ingestion run on same snapshot must add 0 duplicates
        stats_2 = ingest_from_snapshot(repo_id, SNAPSHOT_PATH, session)
        assert stats_2["total_new"] == 0
        assert stats_2["duplicates_skipped"] == stats_1["total_new"]


def test_webhook_hmac_signature_verification():
    secret = "my_super_secret_webhook_key"
    payload = b'{"action": "opened", "number": 42}'

    valid_hash = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    valid_header = f"sha256={valid_hash}"

    assert verify_github_signature(payload, valid_header, secret=secret) is True
    assert verify_github_signature(payload, "sha256=invalid_forged_hash", secret=secret) is False
    assert verify_github_signature(payload, None, secret=secret) is False


def test_webhook_pull_request_enqueues_run(test_db_isolation):
    payload = {
        "action": "opened",
        "repository": {"full_name": "Paramveersingh-S/receipt-demo-shop"},
        "pull_request": {
            "number": 15,
            "title": "feat: Support gift cards at checkout",
            "base": {"sha": "base1234"},
            "head": {"sha": "head5678"},
            "user": {"login": "agent/claude-code"},
        },
    }

    with Session(get_engine()) as session:
        res = handle_webhook_event("pull_request", payload, session)
        assert res["status"] == "enqueued"
        assert res["pr_number"] == 15
        run_id = res["run_id"]

        # Confirm Run was persisted in database
        db_run = session.exec(select(DBRun).where(DBRun.id == run_id)).first()
        assert db_run is not None
        assert db_run.pr_number == 15
        assert db_run.state == "pending"

        # Confirm run.enqueued event was emitted
        events = session.exec(select(DBRunEvent).where(DBRunEvent.run_id == run_id)).all()
        assert any(e.type == "run.enqueued" for e in events)


def test_main_webhook_endpoint_with_signature(test_db_isolation):
    client = TestClient(app)
    payload_dict = {
        "action": "opened",
        "repository": {"full_name": "Paramveersingh-S/receipt-demo-shop"},
        "pull_request": {
            "number": 16,
            "title": "fix: Card expiry date check",
            "base": {"sha": "b111"},
            "head": {"sha": "h222"},
            "user": {"login": "dev-alice"},
        },
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")

    # Generate valid signature with configured secret
    from receipt_api.config import get_settings
    secret = get_settings().github_webhook_secret
    valid_sig = f"sha256={hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()}"

    # 1. Valid signature -> 200 OK
    res = client.post(
        "/webhooks/github",
        content=payload_bytes,
        headers={"X-Hub-Signature-256": valid_sig, "X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "enqueued"

    # 2. Invalid signature -> 401 Unauthorized
    res_bad = client.post(
        "/webhooks/github",
        content=payload_bytes,
        headers={"X-Hub-Signature-256": "sha256=bad_sig", "X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
    )
    assert res_bad.status_code == 401
