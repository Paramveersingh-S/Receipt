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

---

## [Phase 1: Demo Target Repo (`demo/demo-shop`) & Seeding Engine] - 2026-10-26

### What Was Built
- **TipJar Shop (`demo/demo-shop/`)**: Complete FastAPI e-commerce application serving product catalog, shopping cart, and checkout flow with server-rendered Jinja2 HTML templates (`index.html`, `cart.html`, `checkout.html`) for browser QA interaction.
- **Strict Integer Money**: All models (`models.py`, `pricing.py`) represent money in integer cents with half-up rounding in integer arithmetic.
- **Resilient Payment Handling**: Mock payment gateway with idempotency key deduplication, specific exception definitions (`CardDeclinedError`, `GatewayTimeoutError`), and PII redaction (`mask_card_number`).
- **N+1 Avoidance**: Catalog product listing with eager batched relations loading.
- **Auth Dependency**: Protected administrative endpoints guarded by `require_auth`.
- **Seeding & Snapshot (`demo/seed/`)**:
  - `planted_lessons.json`: 7 core planted lessons (idempotency, integer money, no bare except, N+1 query avoidance, auth dependency, PII masking, reversible migrations) referencing authentic PRs/reverts.
  - `snapshot.json`: Full offline snapshot of 11 merged PRs, review discussions, and incident issue resolution threads.
  - `seed_history.py`: Idempotent script for offline cross-validation and live GitHub API seeding.
  - `hidden_tests/test_coupons_hidden.py`: Benchmark held-out test suite validating precision half-up rounding on fractional cent boundaries ($19.99, $29.99) and distinct payment retry idempotency keys.
- **Agent Branches**:
  - `agent/coupons-subtle-bug`: Authored by `agent/claude-code`, adds coupon support that passes its own naive unit tests but introduces float arithmetic `int(subtotal * (pct / 100.0))` and static retry idempotency keys (evading naive unit tests, failing hidden tests).
  - `agent/coupons-correct`: Authored by `agent/claude-code`, correct integer basis point implementation passing both its own unit tests and hidden tests.

### Verification & Measured Results
- `demo/demo-shop/tests`: 16/16 tests passed in 0.83s.
- `coverage report`: 83% line coverage across `demo/demo-shop/shop/` (exceeds ≥ 70% threshold).
- `seed_history.py --validate-only`: 7/7 planted lessons validated with 100% evidence resolution against `snapshot.json`.
- `test_coupons_hidden.py`:
  - On subtle implementation: 3/3 tests FAILED as expected (catching float truncation and static idempotency keys).
  - On correct implementation: 3/3 tests PASSED.
  - On subtle branch's own naive test: PASSED (demonstrating the subtle bug evasion).

### Next Step
Phase 2 (Sandbox runner for safe execution of untrusted PR code with Docker & restricted subprocess backends).

