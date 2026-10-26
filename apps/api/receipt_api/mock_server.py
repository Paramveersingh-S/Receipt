import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "fixtures"


def load_fixture(name: str) -> Any:
    path = FIXTURES_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture {name} not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


app = FastAPI(
    title="Receipt Mock API Server",
    description="Mock server serving contracts/fixtures with streaming SSE event timelines for frontend development",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "mock", "version": "0.1.0"}


# --- Repositories ---
@app.get("/repos")
async def list_repos():
    return [
        {
            "id": "repo_demo_shop",
            "full_name": "Paramveersingh-S/receipt-demo-shop",
            "default_branch": "main",
            "stack": "python",
            "last_ingested_at": "2026-10-26T12:00:00Z",
        }
    ]


@app.get("/repos/{id}")
async def get_repo(id: str):
    return {
        "id": id,
        "full_name": "Paramveersingh-S/receipt-demo-shop",
        "default_branch": "main",
        "stack": "python",
        "last_ingested_at": "2026-10-26T12:00:00Z",
    }


@app.post("/repos/{id}/ingest")
async def start_ingest(id: str):
    return {"status": "started", "repo_id": id, "job_id": "job_ingest_mock"}


@app.get("/repos/{id}/ingest/events")
async def stream_ingest_events(id: str, request: Request, speed: float = 1.0):
    async def timeline_generator():
        path = FIXTURES_DIR / "ingest.events.ndjson"
        delay = max(0.1, 1.0 / max(speed, 0.1))
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if await request.is_disconnected():
                    break
                line = line.strip()
                if line:
                    ev = json.loads(line)
                    yield {"event": ev.get("type", "message"), "data": line}
                    await asyncio.sleep(delay)

    return EventSourceResponse(timeline_generator())


# --- Constraints (Scar Tissue) ---
@app.get("/repos/{id}/constraints")
async def list_constraints(
    id: str,
    q: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
):
    constraints = load_fixture("constraints.list.json")
    if severity:
        constraints = [c for c in constraints if c.get("severity") == severity]
    if status:
        constraints = [c for c in constraints if c.get("status") == status]
    if q:
        q_l = q.lower()
        constraints = [
            c
            for c in constraints
            if q_l in c.get("title", "").lower() or q_l in c.get("rule", "").lower()
        ]
    return constraints


@app.get("/constraints/{id}")
async def get_constraint_detail(id: str):
    return load_fixture("constraint.detail.json")


@app.post("/constraints/{id}/feedback")
async def submit_feedback(id: str, payload: Dict[str, Any]):
    return {"constraint_id": id, "status": "recorded", "action": payload.get("action")}


@app.post("/repos/{id}/briefing")
async def briefing(id: str, payload: Dict[str, Any]):
    constraints = load_fixture("constraints.list.json")[:4]
    return {
        "constraints": constraints,
        "preflight_checklist": [
            "Ensure monetary amounts are stored and calculated as integer cents, never float",
            "Include unique Idempotency-Key on all payment retry attempts",
            "Handle specific GatewayTimeoutError instead of catching bare Exception",
        ],
        "suggested_tests": [
            "test_coupon_rounds_half_up",
            "test_payment_idempotency_key_propagated",
        ],
    }


@app.post("/repos/{id}/check-diff")
async def check_diff(id: str, payload: Dict[str, Any]):
    diff = payload.get("diff", "")
    violations = []
    if "float" in diff or "discount / 100" in diff:
        violations.append(
            {
                "constraint_id": "sc_001",
                "title": "Money is integer cents, never float",
                "severity": "block",
                "file": "shop/pricing.py",
                "line": 42,
                "hunk": "-total * (discount / 100.0)\n+int(round(total * discount_pct))",
                "evidence_urls": [
                    "https://github.com/Paramveersingh-S/receipt-demo-shop/pull/8"
                ],
            }
        )
    return {"violations": violations, "passed": len(violations) == 0}


# --- Runs & Verification ---
@app.get("/repos/{id}/runs")
async def list_runs(id: str):
    return load_fixture("runs.list.json")


@app.get("/runs/{id}")
async def get_run(id: str):
    runs = load_fixture("runs.list.json")
    for r in runs:
        if r.get("id") == id:
            return r
    return runs[0]


@app.post("/repos/{id}/runs")
async def trigger_run(id: str, payload: Dict[str, Any]):
    return {
        "id": "run_001",
        "repo_id": id,
        "pr_number": payload.get("pr_number", 12),
        "base_sha": payload.get("base_sha", "a1b2c3"),
        "head_sha": payload.get("head_sha", "d4e5f6"),
        "state": "running",
        "started_at": "2026-10-26T12:00:00Z",
    }


@app.get("/runs/{id}/events")
async def stream_run_events(id: str, request: Request, speed: float = 1.0):
    async def timeline_generator():
        fixture_name = "run.events.repair.ndjson" if "repair" in id else "run.events.verified.ndjson"
        path = FIXTURES_DIR / fixture_name
        delay = max(0.05, 0.8 / max(speed, 0.1))
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if await request.is_disconnected():
                    break
                line = line.strip()
                if line:
                    ev = json.loads(line)
                    yield {"event": ev.get("type", "message"), "data": line}
                    await asyncio.sleep(delay)

    return EventSourceResponse(timeline_generator())


# --- Receipts ---
@app.get("/receipts/{id}")
async def get_receipt(id: str):
    if "reject" in id.lower():
        return load_fixture("receipt.rejected.json")
    if "review" in id.lower():
        return load_fixture("receipt.needs_review.json")
    return load_fixture("receipt.verified.json")


@app.get("/r/{slug}")
async def get_public_receipt(slug: str):
    if slug == "m4p9q2":
        return load_fixture("receipt.rejected.json")
    if slug == "k8w1v3":
        return load_fixture("receipt.needs_review.json")
    return load_fixture("receipt.verified.json")


@app.get("/receipts/{id}/markdown")
async def get_receipt_markdown(id: str):
    r = load_fixture("receipt.verified.json")
    return PlainTextResponse(f"# Verification Receipt: {r['verdict']} (Score: {r['score']}/100)\nPR #{r['pr']['number']}")


@app.post("/receipts/{id}/outcomes")
async def submit_outcome(id: str, payload: Dict[str, Any]):
    return {"receipt_id": id, "status": "recorded"}


# --- Graph & Stats & Bench ---
@app.get("/repos/{id}/graph")
async def get_graph(id: str):
    return load_fixture("graph.json")


@app.get("/repos/{id}/stats")
async def get_stats(id: str):
    return load_fixture("stats.json")


@app.get("/repos/{id}/docs")
async def get_docs(id: str):
    return {
        "pitfalls": "# Known Pitfalls\n- Money must be integer cents.\n- Always pass idempotency keys.",
        "decisions": "# Decision Log\n- Reverted PR #7 due to float drift.",
        "weekly_digest": "# Weekly Memory Digest\n- 3 new constraints identified from reviews.",
    }


@app.post("/repos/{id}/docs/sync")
async def sync_docs(id: str):
    return {
        "status": "synchronized",
        "pr_url": "https://github.com/Paramveersingh-S/receipt-demo-shop/pull/21",
        "updated_files": ["AGENTS.md", "docs/scar/pitfalls.md"],
    }


@app.get("/bench/results")
async def get_bench():
    return load_fixture("bench.results.json")


@app.get("/artifacts/{id}")
async def get_artifact(id: str):
    return {"id": id, "url": f"/artifacts/{id}", "kind": "diff", "content": "Diff artifact preview"}


@app.post("/webhooks/github")
async def webhook(payload: Dict[str, Any]):
    return {"status": "ok"}
