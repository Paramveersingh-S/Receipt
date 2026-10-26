# Build Log — Receipt

Tracks chronological progress across each phase, including problem solved, trade-offs, results, and next steps.

---

## [Phase 0: Foundation, Contracts & Fixtures] - 2026-10-26

### What Was Built
- Repository foundation per AGENTS.md layout: `AGENTS.md`, `.agent/workflows/` (`phase.md`, `redteam.md`, `log.md`, `slice-check.md`), `.gitignore`, `Makefile`, `.env.example`, and architectural documentation.
- FastAPI core application (`apps/api/receipt_api/main.py`) exposing the complete 24-endpoint REST surface specified in plan §B6.
- Database engine and models (`db.py`, `models.py`) with SQLite WAL mode, foreign keys, and FTS5 full-text indexing for constraints.
- Provider-agnostic LLM client (`llm/client.py`) with SQLite response cache, `LLM_MODE=live|record|replay`, tenacity exponential backoff, and Pydantic structured output validation with automatic repair loop (max 2 retries).
- Persistent replayable event streaming (`events.py`) supporting SSE `?after_seq=` query and in-process async pub/sub bus.
- Persistent SQLite-backed background job queue and async worker (`jobs.py`).
- Complete contract specifications and fixtures (`contracts/`):
  - Generated `openapi.json` (59KB, 24 endpoints)
  - `events.schema.json`
  - All 11 fixtures in `contracts/fixtures/`: `receipt.verified.json`, `receipt.rejected.json`, `receipt.needs_review.json`, `constraints.list.json` (15 rich constraints with real evidence), `constraint.detail.json`, `graph.json`, `stats.json`, `runs.list.json`, `bench.results.json`, `ingest.events.ndjson`, `run.events.verified.ndjson`, `run.events.repair.ndjson`.
- Mock server (`receipt_api/mock_server.py`) serving fixtures and timed SSE streaming over port 8000 for Claude's frontend track.
- Automated end-to-end smoke test script (`scripts/demo_smoke.py`).

### Verification & Measured Results
- `make test`: 16/16 tests passed in 5.70s.
- `make lint`: Syntax and compilation check passed with 0 errors.
- `make demo-smoke`: Full loop smoke check passed with ASCII verification receipt output.
- `make mock`: Server verified at `http://127.0.0.1:8000/health` (200 OK) and SSE timeline streamed cleanly on `/runs/demo/events`.

### Next Step
Hand `contracts/` and `make mock` to Claude for UI design track; begin Phase 1 (Demo target repo `demo/demo-shop` and seeding scripts).

