import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse
import structlog
from receipt_api.config import get_settings
from receipt_api.db import init_db
from receipt_api.events import stream_run_events
from receipt_api.jobs import job_queue
from receipt_api.schemas import (
    BriefingRequest,
    BriefingResponse,
    CheckDiffRequest,
    CheckDiffResponse,
    ConstraintFeedbackRequest,
    ConstraintSchema,
    CreateRepoRequest,
    CreateRunRequest,
    DocsSyncResponse,
    GraphResponse,
    OutcomeRequest,
    ReceiptSchema,
    RepoResponse,
    RunResponse,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "fixtures"


def load_fixture(filename: str) -> Any:
    path = CONTRACTS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and FTS5 index
    init_db()
    logger.info("Receipt database and FTS5 initialized")
    yield
    job_queue.stop_worker()


app = FastAPI(
    title="Receipt API",
    description="Automated verification and institutional memory for agent-written code",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0", "mode": settings.llm_mode}


# --- Repositories ---
@app.post("/repos", response_model=RepoResponse, tags=["repos"])
async def create_repo(req: CreateRepoRequest):
    repo_id = f"repo_{req.full_name.replace('/', '_')}"
    return RepoResponse(
        id=repo_id,
        full_name=req.full_name,
        default_branch=req.default_branch,
        stack="python",
    )


@app.get("/repos", response_model=List[RepoResponse], tags=["repos"])
async def list_repos():
    return [
        RepoResponse(
            id="repo_Paramveersingh-S_receipt-demo-shop",
            full_name="Paramveersingh-S/receipt-demo-shop",
            default_branch="main",
            stack="python",
        )
    ]


@app.get("/repos/{id}", response_model=RepoResponse, tags=["repos"])
async def get_repo(id: str):
    return RepoResponse(
        id=id,
        full_name="Paramveersingh-S/receipt-demo-shop",
        default_branch="main",
        stack="python",
    )


@app.post("/repos/{id}/ingest", tags=["repos"])
async def trigger_ingest(id: str):
    job_id = job_queue.enqueue("ingest_repo", {"repo_id": id})
    return {"status": "queued", "job_id": job_id, "repo_id": id}


@app.get("/repos/{id}/ingest/events", tags=["repos"])
async def stream_ingest_events(id: str, request: Request, speed: float = 1.0):
    async def event_generator():
        ndjson_path = CONTRACTS_DIR / "ingest.events.ndjson"
        if ndjson_path.exists():
            with open(ndjson_path, "r", encoding="utf-8") as f:
                for line in f:
                    if await request.is_disconnected():
                        break
                    line = line.strip()
                    if line:
                        yield {"data": line}
    return EventSourceResponse(event_generator())


# --- Constraints (Scar Tissue) ---
@app.get("/repos/{id}/constraints", response_model=List[ConstraintSchema], tags=["scar"])
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
        q_lower = q.lower()
        constraints = [
            c
            for c in constraints
            if q_lower in c.get("title", "").lower() or q_lower in c.get("rule", "").lower()
        ]
    return constraints


@app.get("/constraints/{id}", response_model=ConstraintSchema, tags=["scar"])
async def get_constraint(id: str):
    detail = load_fixture("constraint.detail.json")
    if detail.get("id") == id or id == "sc_001":
        return detail
    constraints = load_fixture("constraints.list.json")
    for c in constraints:
        if c.get("id") == id:
            return c
    raise HTTPException(status_code=404, detail="Constraint not found")


@app.post("/constraints/{id}/feedback", tags=["scar"])
async def constraint_feedback(id: str, req: ConstraintFeedbackRequest):
    return {"constraint_id": id, "status": "updated", "action": req.action}


@app.post("/repos/{id}/briefing", response_model=BriefingResponse, tags=["scar"])
async def get_briefing(id: str, req: BriefingRequest):
    constraints = load_fixture("constraints.list.json")[:4]
    return BriefingResponse(
        constraints=constraints,
        preflight_checklist=[
            "Ensure monetary calculations use integer cents, never float",
            "Verify payment retry operations include unique idempotency key",
            "Handle specific gateway exceptions rather than catching bare Exception",
        ],
        suggested_tests=[
            "test_coupon_rounds_half_up",
            "test_payment_idempotency_key_propagated",
        ],
    )


@app.post("/repos/{id}/check-diff", response_model=CheckDiffResponse, tags=["scar"])
async def check_diff(id: str, req: CheckDiffRequest):
    violations = []
    if "total * (discount / 100.0)" in req.diff or "float(" in req.diff:
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
    return CheckDiffResponse(violations=violations, passed=len(violations) == 0)


# --- Runs & Verification ---
@app.post("/repos/{id}/runs", response_model=RunResponse, tags=["verify"])
async def create_run(id: str, req: CreateRunRequest):
    run_id = f"run_{os.urandom(4).hex()}"
    return RunResponse(
        id=run_id,
        repo_id=id,
        pr_number=req.pr_number,
        base_sha=req.base_sha,
        head_sha=req.head_sha,
        state="pending",
        started_at=load_fixture("runs.list.json")[0]["started_at"],
    )


@app.get("/repos/{id}/runs", tags=["verify"])
async def list_repo_runs(id: str):
    return load_fixture("runs.list.json")


@app.get("/runs/{id}", tags=["verify"])
async def get_run(id: str):
    runs = load_fixture("runs.list.json")
    for r in runs:
        if r.get("id") == id:
            return r
    return runs[0]


@app.get("/runs/{id}/events", tags=["verify"])
async def get_run_events(id: str, request: Request, after_seq: int = 0):
    async def sse_adapter():
        async for ev in stream_run_events(id, after_seq=after_seq):
            if await request.is_disconnected():
                break
            yield {"event": ev["type"], "data": json.dumps(ev)}

    return EventSourceResponse(sse_adapter())


# --- Receipts ---
@app.get("/receipts/{id}", response_model=ReceiptSchema, tags=["receipts"])
async def get_receipt(id: str):
    from sqlmodel import Session, select
    from receipt_api.db import get_engine
    from receipt_api.models import DBReceipt

    try:
        with Session(get_engine()) as session:
            db_r = session.exec(select(DBReceipt).where(DBReceipt.id == id)).first()
            if db_r:
                return json.loads(db_r.receipt_json) if isinstance(db_r.receipt_json, str) else db_r.receipt_json
    except Exception:
        pass

    if "reject" in id.lower():
        return load_fixture("receipt.rejected.json")
    if "review" in id.lower():
        return load_fixture("receipt.needs_review.json")
    return load_fixture("receipt.verified.json")


@app.get("/r/{slug}", response_model=ReceiptSchema, tags=["receipts"])
async def get_receipt_by_slug(slug: str):
    from sqlmodel import Session, select
    from receipt_api.db import get_engine
    from receipt_api.models import DBReceipt

    try:
        with Session(get_engine()) as session:
            db_r = session.exec(select(DBReceipt).where(DBReceipt.public_slug == slug)).first()
            if db_r:
                return json.loads(db_r.receipt_json) if isinstance(db_r.receipt_json, str) else db_r.receipt_json
    except Exception:
        pass

    if slug == "m4p9q2":
        return load_fixture("receipt.rejected.json")
    if slug == "k8w1v3":
        return load_fixture("receipt.needs_review.json")
    return load_fixture("receipt.verified.json")


@app.get("/receipts/{id}/markdown", response_class=PlainTextResponse, tags=["receipts"])
async def get_receipt_markdown(id: str):
    from sqlmodel import Session, select
    from receipt_api.db import get_engine
    from receipt_api.models import DBReceipt
    from receipt_api.verify.receipt import format_receipt_markdown

    try:
        with Session(get_engine()) as session:
            db_r = session.exec(select(DBReceipt).where((DBReceipt.id == id) | (DBReceipt.public_slug == id))).first()
            if db_r:
                payload = json.loads(db_r.receipt_json) if isinstance(db_r.receipt_json, str) else db_r.receipt_json
                return format_receipt_markdown(ReceiptSchema(**payload))
    except Exception:
        pass

    r = load_fixture("receipt.verified.json")
    return format_receipt_markdown(ReceiptSchema(**r))


@app.post("/receipts/{id}/outcomes", tags=["receipts"])
async def record_outcome(id: str, req: OutcomeRequest):
    return {"receipt_id": id, "decision": req.human_decision, "status": "recorded"}


# --- Graph & Stats & Docs ---
@app.get("/repos/{id}/graph", response_model=GraphResponse, tags=["graph"])
async def get_graph(id: str):
    return load_fixture("graph.json")


@app.get("/repos/{id}/stats", tags=["stats"])
async def get_stats(id: str):
    return load_fixture("stats.json")


@app.get("/repos/{id}/docs", tags=["docs"])
async def get_docs(id: str):
    return {
        "pitfalls": "# Known Pitfalls\n- Money must be integer cents.\n- Always pass idempotency keys.",
        "decisions": "# Decision Log\n- Reverted PR #7 due to float drift.",
        "weekly_digest": "# Weekly Memory Digest\n- 3 new constraints identified from reviews.",
    }


@app.post("/repos/{id}/docs/sync", response_model=DocsSyncResponse, tags=["docs"])
async def sync_docs(id: str):
    return DocsSyncResponse(
        status="synchronized",
        pr_url="https://github.com/Paramveersingh-S/receipt-demo-shop/pull/21",
        updated_files=["AGENTS.md", "docs/scar/pitfalls.md"],
    )


@app.get("/bench/results", tags=["bench"])
async def get_bench_results():
    return load_fixture("bench.results.json")


# --- Artifacts & Webhooks ---
@app.get("/artifacts/{id}", tags=["artifacts"])
async def get_artifact(id: str):
    return {
        "id": id,
        "content": "Artifact data payload (logs, test reports, or screenshot blobs)",
        "kind": "test",
    }


@app.post("/webhooks/github", tags=["webhooks"])
async def github_webhook(request: Request):
    payload = await request.json()
    action = payload.get("action")
    return {"status": "received", "action": action}
