import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure apps/api is in sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir / "apps" / "api"))

import structlog
structlog.configure(logger_factory=structlog.PrintLoggerFactory(sys.stderr))

from sqlmodel import Session, select
from receipt_api.db import session_scope as get_session
from receipt_api.models import ConstraintRecord, DBRun, ReceiptRecord, Repo
from receipt_api.scar.briefing import generate_briefing
from receipt_api.scar.checks import run_static_checks_on_diff
from receipt_api.scar.learning import record_receipt_outcome
from receipt_api.scar.retrieve import search_constraints


def handle_receipt_briefing(task: str, paths: Optional[List[str]] = None) -> str:
    """Pre-coding briefing tool for agents."""
    with get_session() as session:
        # Pick the first repo or demo-shop repo
        repo = session.exec(select(Repo)).first()
        repo_id = repo.id if repo else "repo_demo_shop"
        briefing = generate_briefing(
            repo_id=repo_id,
            task=task,
            paths=paths or [],
            session=session,
        )
        return briefing.to_markdown()


def handle_receipt_check_diff(diff: str) -> str:
    """Check a candidate unified diff against Scar Tissue static invariant checks."""
    violations = run_static_checks_on_diff(diff)
    if not violations:
        return "✅ All Scar Tissue institutional constraints satisfied! Zero invariant violations detected."

    output = [f"⚠️ Found {len(violations)} Scar Tissue constraint violation(s) in candidate diff:\n"]
    for v in violations:
        loc = f"{v.file}:{v.line}" if v.file else "diff"
        output.append(f"- ❌ [{v.check_id}] at {loc}: {v.message}")
        suggestion = getattr(v, "suggestion", None)
        if suggestion:
            output.append(f"   💡 Recommendation: {suggestion}")
    return "\n".join(output)


def handle_receipt_verify_pr(repo: str, pr: int) -> str:
    """Trigger or query verification pipeline for a pull request."""
    with get_session() as session:
        run = session.exec(
            select(DBRun)
            .where(DBRun.pr_number == pr)
            .order_by(DBRun.started_at.desc())
        ).first()

        if run:
            receipt = session.exec(
                select(ReceiptRecord).where(ReceiptRecord.run_id == run.id)
            ).first()
            if receipt:
                return (
                    f"Receipt for {repo} PR #{pr}:\n"
                    f"- Verdict: {receipt.verdict}\n"
                    f"- Score: {receipt.score}/100\n"
                    f"- Receipt ID: {receipt.id}\n"
                    f"- Public Slug: {receipt.public_slug}"
                )
            return f"Verification run '{run.id}' for {repo} PR #{pr} is currently in state: '{run.state}'."

        return (
            f"Enqueued verification for {repo} PR #{pr}. "
            "Sandbox pipeline will verify acceptance criteria proofs, regression, mutation score, and institutional constraints."
        )


def handle_receipt_get_receipt(id_or_slug: str) -> str:
    """Retrieve full verification receipt by ID or public slug."""
    with get_session() as session:
        receipt = session.exec(
            select(ReceiptRecord).where(
                (ReceiptRecord.id == id_or_slug) | (ReceiptRecord.public_slug == id_or_slug)
            )
        ).first()

        if not receipt:
            return f"Receipt '{id_or_slug}' not found."

        try:
            data = json.loads(receipt.receipt_json)
            from receipt_api.github.statuses import format_receipt_markdown
            return format_receipt_markdown(data)
        except Exception:
            return receipt.receipt_json


def handle_receipt_feedback(run_id: str) -> str:
    """Retrieve failure bundle for an external agent to repair."""
    with get_session() as session:
        run = session.exec(select(DBRun).where(DBRun.id == run_id)).first()
        if not run:
            return f"Run '{run_id}' not found."

        receipt = session.exec(select(ReceiptRecord).where(ReceiptRecord.run_id == run.id)).first()
        if not receipt:
            return f"Run '{run_id}' does not have a completed receipt yet."

        if receipt.verdict == "VERIFIED":
            return f"Run '{run_id}' passed verification with verdict VERIFIED ({receipt.score}/100). No repair needed."

        data = json.loads(receipt.receipt_json)
        from receipt_api.repair.external import ExternalAgentRepair
        from receipt_api.repair.patcher import FailureBundle
        bundle = FailureBundle(
            failed_proofs=[c.get("description", "") for c in data.get("acceptance_criteria", []) if c.get("status") != "PASS"],
            test_tracebacks=data.get("proofs", {}).get("tracebacks", []),
            violated_constraints=[c.get("title") or c.get("id") for c in data.get("constraints", []) if c.get("status") in ("VIOLATED", "FAIL")],
            surviving_mutants=[s.get("op", "") for s in data.get("mutation", {}).get("survivors", [])],
        )
        return ExternalAgentRepair.format_failure_markdown(run_id, bundle, score=receipt.score)


def handle_receipt_report_outcome(receipt_id: str, decision: str, note: str = "") -> str:
    """Record merge/review outcome and update institutional memory confidence."""
    try:
        res = record_receipt_outcome(receipt_id=receipt_id, human_decision=decision, note=note)
        adjustments = res.get("adjusted_constraints", [])
        return (
            f"Outcome '{decision}' successfully recorded for receipt '{receipt_id}'.\n"
            f"Updated {len(adjustments)} institutional constraints in the learning loop."
        )
    except Exception as e:
        return f"Failed to record outcome: {str(e)}"


def handle_scar_search(query: str) -> str:
    """Search institutional constraints using hybrid retrieval (FTS5 + vectors)."""
    with get_session() as session:
        repo = session.exec(select(Repo)).first()
        repo_id = repo.id if repo else "repo_demo_shop"
        constraints = search_constraints(repo_id=repo_id, query=query, session=session, top_k=5)
        if not constraints:
            return f"No constraints matching query: '{query}'."

        lines = [f"Found {len(constraints)} matching Scar Tissue constraints:\n"]
        for c in constraints:
            area = getattr(c, "area", "general")
            lines.append(f"- **{c.title}** (`{c.id}`, Area: `{area}`, Confidence: {int(c.confidence*100)}%)")
            lines.append(f"  {c.why}")
        return "\n".join(lines)


def handle_resource_constraints_path(path: str) -> str:
    """Read resource scar://constraints/{path}."""
    with get_session() as session:
        repo = session.exec(select(Repo)).first()
        repo_id = repo.id if repo else "repo_demo_shop"
        constraints = session.exec(
            select(ConstraintRecord)
            .where(ConstraintRecord.repo_id == repo_id)
            .where(ConstraintRecord.status == "active")
        ).all()

        matching = []
        path_lower = path.lower()
        for c in constraints:
            if "pricing" in path_lower or "coupon" in path_lower or "checkout" in path_lower:
                if c.area in ("money_and_pricing", "api_and_idempotency"):
                    matching.append(c)
            else:
                matching.append(c)

        lines = [f"# Scar Tissue Constraints for path: `{path}`\n"]
        for c in matching[:5]:
            lines.append(f"## {c.title} (`{c.id}`)")
            lines.append(f"- Gate: `{c.gate}` | Confidence: `{int(c.confidence*100)}%`")
            lines.append(f"- Rationale: {c.rationale}\n")
        return "\n".join(lines)


# Tool definitions matching the standard MCP Tool Schema
MCP_TOOLS = [
    {
        "name": "receipt_briefing",
        "description": "Get pre-coding briefing with active institutional constraints, traps, and suggested tests before modifying code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task description or ticket prompt."},
                "paths": {"type": "array", "items": {"type": "string"}, "description": "Target file paths to be touched."},
            },
            "required": ["task"],
        },
    },
    {
        "name": "receipt_check_diff",
        "description": "Check a unified diff against Scar Tissue AST static invariant checks before creating a commit or PR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "Unified git diff text."},
            },
            "required": ["diff"],
        },
    },
    {
        "name": "receipt_verify_pr",
        "description": "Trigger or query sandbox verification for a pull request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Full repository name (e.g. Paramveersingh-S/Receipt)."},
                "pr": {"type": "integer", "description": "Pull request number."},
            },
            "required": ["repo", "pr"],
        },
    },
    {
        "name": "receipt_get_receipt",
        "description": "Fetch a verification receipt by ID or public slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Receipt ID or public slug."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "receipt_feedback",
        "description": "Fetch structured failure bundle and diagnostic instructions for an external agent to repair a failed PR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Verification run ID."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "receipt_report_outcome",
        "description": "Report a human or PR merge decision ('merged', 'rejected', 'overridden') to train the Scar Tissue learning loop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "receipt_id": {"type": "string", "description": "Receipt ID."},
                "decision": {"type": "string", "enum": ["merged", "rejected", "overridden"], "description": "Human or merge decision."},
                "note": {"type": "string", "description": "Optional human rationale."},
            },
            "required": ["receipt_id", "decision"],
        },
    },
    {
        "name": "scar_search",
        "description": "Search the Scar Tissue institutional memory for constraints, lessons, and past incidents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language or keyword search query."},
            },
            "required": ["query"],
        },
    },
]


def process_jsonrpc_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a single JSON-RPC 2.0 MCP request."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": "receipt-mcp-server",
                    "version": "1.0.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": MCP_TOOLS,
            },
        }

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        result_text = ""
        try:
            if name == "receipt_briefing":
                result_text = handle_receipt_briefing(task=args.get("task", ""), paths=args.get("paths", []))
            elif name == "receipt_check_diff":
                result_text = handle_receipt_check_diff(diff=args.get("diff", ""))
            elif name == "receipt_verify_pr":
                result_text = handle_receipt_verify_pr(repo=args.get("repo", ""), pr=args.get("pr", 0))
            elif name == "receipt_get_receipt":
                result_text = handle_receipt_get_receipt(id_or_slug=args.get("id", ""))
            elif name == "receipt_feedback":
                result_text = handle_receipt_feedback(run_id=args.get("run_id", ""))
            elif name == "receipt_report_outcome":
                result_text = handle_receipt_report_outcome(
                    receipt_id=args.get("receipt_id", ""),
                    decision=args.get("decision", ""),
                    note=args.get("note", ""),
                )
            elif name == "scar_search":
                result_text = handle_scar_search(query=args.get("query", ""))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method/Tool '{name}' not found"},
                }
        except Exception as e:
            result_text = f"Error executing tool '{name}': {str(e)}"

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ]
            },
        }

    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resources": [
                    {
                        "uri": "scar://constraints/{path}",
                        "name": "Scar Tissue Constraints",
                        "description": "Active institutional constraints and invariant rules for a repository file path.",
                        "mimeType": "text/markdown",
                    }
                ]
            },
        }

    if method == "resources/read":
        uri = params.get("uri", "")
        if uri.startswith("scar://constraints/"):
            path = uri[len("scar://constraints/"):]
            text = handle_resource_constraints_path(path)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/markdown",
                            "text": text,
                        }
                    ]
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": f"Unknown resource URI: {uri}"},
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unsupported method: {method}"},
    }


def run_stdio() -> None:
    """Run JSON-RPC 2.0 stdio event loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = process_jsonrpc_request(req)
            if res is not None:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Receipt FastMCP Server")
    parser.add_argument("--stdio", action="store_true", default=True, help="Run stdio JSON-RPC loop")
    args = parser.parse_args()
    run_stdio()
