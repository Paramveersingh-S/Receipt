import json
import subprocess
import pytest
from pathlib import Path
from sqlmodel import Session, select

from receipt_api.db import session_scope
from receipt_api.github.statuses import RECEIPT_COMMENT_MARKER, format_receipt_markdown
from receipt_api.models import Constraint, Outcome, ReceiptRecord, Repo
from receipt_api.scar.docs_gen import (
    AGENTS_MD_BEGIN,
    AGENTS_MD_END,
    sync_living_docs,
    update_agents_md_file,
)
from receipt_api.scar.learning import record_receipt_outcome, get_learning_stats


def test_github_status_markdown_formatting():
    receipt_data = {
        "id": "rcpt_test_001",
        "verdict": "VERIFIED",
        "score": 91,
        "public_slug": "rcpt-demo-slug",
        "score_breakdown": {
            "proofs": 95,
            "regression": 100,
            "test_strength": 85,
            "constraints": 100,
            "browser": 90,
        },
        "acceptance_criteria": [
            {
                "description": "Applies 15% discount coupon",
                "kind": "feature",
                "base_status": "FAIL",
                "head_status": "PASS",
                "status": "PASS",
            }
        ],
        "constraints": [
            {"id": "sc_float_cents", "title": "Use integer cents", "status": "PASS"}
        ],
        "mutation": {
            "applicable": True,
            "killed": 15,
            "total": 16,
            "survivors": [],
        },
        "repair_history": [
            {"iteration": 1, "score": 48},
            {"iteration": 2, "score": 91},
        ],
    }

    md = format_receipt_markdown(receipt_data, public_url="https://receipt.dev")
    assert RECEIPT_COMMENT_MARKER in md
    assert "## 🧾 Receipt Verification Report: `✅ VERIFIED`" in md
    assert "**Overall Score:** `91/100`" in md
    assert "https://receipt.dev/r/rcpt-demo-slug" in md
    assert "Acceptance Criteria Proof Matrix" in md
    assert "Iter 1: `48/100` → Iter 2: `91/100`" in md


def test_mcp_server_tools():
    # Test JSON-RPC over stdio subprocess
    cmd = [".venv/Scripts/python.exe", "mcp_server.py"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # 1. Initialize
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
    # 2. List tools
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
    # 3. Call receipt_check_diff
    diff_bad = """--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -10,1 +10,1 @@
+    return price * 0.15
"""
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "receipt_check_diff", "arguments": {"diff": diff_bad}}
    }) + "\n")
    proc.stdin.flush()

    line1 = proc.stdout.readline()
    res1 = json.loads(line1)
    assert res1["result"]["serverInfo"]["name"] == "receipt-mcp-server"

    line2 = proc.stdout.readline()
    res2 = json.loads(line2)
    tool_names = [t["name"] for t in res2["result"]["tools"]]
    assert "receipt_briefing" in tool_names
    assert "receipt_check_diff" in tool_names
    assert "receipt_verify_pr" in tool_names
    assert "scar_search" in tool_names

    line3 = proc.stdout.readline()
    res3 = json.loads(line3)
    content_text = res3["result"]["content"][0]["text"]
    assert "float-money" in content_text or "violation" in content_text or "integer" in content_text

    proc.terminate()


def test_living_docs_generation(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    agents_md = repo_dir / "AGENTS.md"
    agents_md.write_text("# Target Repo Rules\n\nExisting instructions...\n", encoding="utf-8")

    with session_scope() as session:
        # Create a test repo and constraint
        repo = Repo(id="repo_docs_test", full_name="Paramveersingh-S/docs-test")
        session.add(repo)
        c = Constraint(
            id="sc_test_docs_rule",
            repo_id="repo_docs_test",
            title="Always Use Integer Cents",
            rule="Never store monetary amounts as float numbers.",
            why="Prevents accumulated IEEE 754 precision errors.",
            severity="block",
            confidence=0.95,
            status="active",
            prevented_count=4,
        )
        session.add(c)
        session.commit()

        # Run living docs sync
        res = sync_living_docs(repo_id="repo_docs_test", repo_path=repo_dir, session=session)
        assert res["status"] == "success"

        # Check generated docs
        pitfalls = (repo_dir / "docs" / "scar" / "pitfalls.md").read_text(encoding="utf-8")
        assert "Always Use Integer Cents" in pitfalls
        assert "sc_test_docs_rule" in pitfalls

        decisions = (repo_dir / "docs" / "scar" / "decisions.md").read_text(encoding="utf-8")
        assert "Always Use Integer Cents" in decisions

        digest = (repo_dir / "docs" / "scar" / "digest.md").read_text(encoding="utf-8")
        assert "Weekly Scar Tissue Memory Digest" in digest

        # Check AGENTS.md updated block
        updated_agents = agents_md.read_text(encoding="utf-8")
        assert AGENTS_MD_BEGIN in updated_agents
        assert AGENTS_MD_END in updated_agents
        assert "Always Use Integer Cents" in updated_agents


def test_learning_loop_outcome_recording():
    with session_scope() as session:
        # Setup receipt with constraint
        c = Constraint(
            id="sc_learning_test",
            repo_id="repo_learn_test",
            title="Idempotency Key Required",
            rule="Network endpoints must accept idempotency keys.",
            why="Prevents double billing.",
            severity="block",
            confidence=0.80,
            status="active",
            prevented_count=2,
        )
        session.add(c)

        receipt_json = json.dumps({
            "id": "rcpt_learn_001",
            "verdict": "REJECTED",
            "score": 45,
            "constraints": [
                {"id": "sc_learning_test", "title": "Idempotency Key Required", "status": "VIOLATED"}
            ]
        })
        receipt = ReceiptRecord(
            id="rcpt_learn_001",
            run_id="run_learn_001",
            verdict="REJECTED",
            score=45,
            receipt_json=receipt_json,
            public_slug="slug_learn_001",
        )
        session.add(receipt)
        session.commit()

        # 1. Rejecting PR reinforces the constraint
        res = record_receipt_outcome("rcpt_learn_001", "rejected", session=session)
        assert res["decision"] == "rejected"

        c_updated = session.exec(select(Constraint).where(Constraint.id == "sc_learning_test")).first()
        assert c_updated.confidence > 0.80  # Increased
        assert c_updated.prevented_count == 3  # Incremented

        # 2. Overriding PR penalizes the constraint
        res2 = record_receipt_outcome("rcpt_learn_001", "overridden", session=session)
        c_penalized = session.exec(select(Constraint).where(Constraint.id == "sc_learning_test")).first()
        assert c_penalized.confidence < 0.85  # Decreased


def test_api_endpoints_phase9():
    from fastapi.testclient import TestClient
    from receipt_api.main import app

    client = TestClient(app)

    # 1. Docs sync endpoint
    res_sync = client.post("/repos/repo_demo_shop/docs/sync")
    assert res_sync.status_code == 200
    data_sync = res_sync.json()
    assert data_sync["status"] == "synchronized"
    assert "AGENTS.md" in data_sync["updated_files"]

    # 2. Alan verify webhook endpoint
    res_alan = client.post("/integrations/alan/verify", json={
        "repo": "Paramveersingh-S/receipt-demo-shop",
        "pr": 42,
        "task": "Add discount coupon"
    })
    assert res_alan.status_code == 200
    assert res_alan.json()["agent"] == "alan"
    assert res_alan.json()["status"] == "enqueued"
