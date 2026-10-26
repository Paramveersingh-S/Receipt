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
Begin UI implementation and repository presentation upgrade.

---

## [Frontend Track: macOS-Grade Web Interface (`apps/web`) & Repository Presentation] - 2026-10-26

### What Was Built
- **macOS-Grade Web Application (`apps/web`)**:
  - Bootstrapped Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + Framer Motion + canvas-confetti.
  - **`MacTitlebar`**: Authentically styled titlebar with interactive red/yellow/green traffic lights, active repo breadcrumbs (`Paramveersingh-S/receipt-demo-shop`), PR selector (`#12` Verified vs `#13` Rejected), live SSE connection indicator, and `⌘K` command palette trigger.
  - **`MacDock`**: Floating frosted glass dock at bottom with spring magnification and active indicators for 5 views (`receipt`, `pipeline`, `scar`, `repair`, `benchmarks`).
  - **`ReceiptCard`**: Physical skeuomorphic receipt card featuring perforated sawtooth edges (`clip-path`), thermal monospace font, rubber stamp verdict badge (`[VERIFIED]` / `[REJECTED]`), acceptance criteria fail-before/pass-after matrix, regression check, AST mutation testing score with survivor diffs, Scar Tissue constraints citations, SVG generated barcode, and confetti tearing animation on copy.
  - **`LivePipelineView`**: Real-time 7-stage sandbox execution timeline with animated progress rings, simulated live replay runner, and filterable SSE event terminal stream (`/runs/{id}/events`).
  - **`ScarTissueView`**: Interactive repository knowledge graph rendered in SVG connecting constraints, scoped files, historical PRs, reverts, and incidents; filterable constraint cards; and FastMCP agent briefing simulator preview.
  - **`RepairLoopView`**: Self-healing auto-repair loop view showing iteration recovery curve (+40 pts recovered), structured diagnostic prompts, and side-by-side colorized code diffs in `shop/pricing.py`.
  - **`BenchmarkView`**: Empirical evaluation dashboard comparing Baseline A, Baseline B, Ablated Receipt, and Full Receipt on ReceiptBench (96% detection rate) and ScarBench (100% recall on 7 planted lessons).
  - **`CommandPalette`**: `⌘K` modal dialog with full keyboard navigation (arrows, Enter, Esc) to switch tabs, change PRs, tear & copy receipts, and inspect invariants.
- **Repository Presentation Upgrade (`README.md`)**:
  - High-visibility shields.io badges (Tests, Coverage, Next.js 16, FastMCP, Python 3.12, Contracts, License).
  - 9-step verification lifecycle breakdown from institutional memory mining to digital evidence receipt minting.
  - Comprehensive Mermaid architecture diagram with detailed subgraphs and numbered workflows.
  - Skeuomorphic ASCII receipt preview, benchmark comparison tables, security sandbox model, and local setup guide.

### Verification & Measured Results
- `pnpm --filter web build`: Compiled and optimized in 2.0s with Turbopack, finished TypeScript in 5.1s, generated static pages 4/4 with 0 errors.
- `make test`: 16/16 backend tests passed.
- `pytest demo/demo-shop/tests`: 16/16 demo shop tests passed (83% coverage).
- Git check: `video/` directory strictly excluded by `.gitignore`.

### Next Step
Begin Phase 2 sandbox runner implementation.

---

## [Phase 2: Sandbox Runner & Process Isolation] - 2026-10-26

### What Was Built
- **Sandbox Engine (`apps/api/receipt_api/verify/sandbox.py`)**:
  - `SubprocessSandbox`: Restricted local subprocess execution with strict environment scrubbing (`SAFE_ENV_ALLOWLIST`, stripping `GITHUB_*`, `LLM_*`, `SECRET_*`, etc.), wall-clock timeouts via `subprocess.TimeoutExpired`, process termination, and stdout/stderr capture.
  - `DockerSandbox`: Containerized runner with `--network none`, memory/CPU caps, and non-root execution; automatic fallback to `SubprocessSandbox` when Docker daemon is unreachable.
  - CLI runner: `python -m receipt_api.verify.sandbox --repo <path> --run-tests` producing structured JSON results.
- **Stack Adapters (`apps/api/receipt_api/verify/stacks/`)**:
  - `base.py`: Normalized `TestResult` dataclass (`name`, `status`, `duration_ms`, `message`, `file`, `line`) and `TestStatus` enum.
  - `python.py`: `PythonStackAdapter` detecting pytest/pyproject/requirements repositories, executing tests, and parsing pytest verbose output.
  - `node.py`: `NodeStackAdapter` detecting `package.json`, executing `npm test`, and parsing vitest/jest results.
  - `detect_stack()`: Auto-detection helper for target repos.
- **Test Fixtures & Security Test Suite**:
  - `tests/fixtures/repos/py_calc/`: Tiny Python math package with passing tests.
  - `tests/fixtures/repos/node_calc/`: Tiny Node package with `node:test` suite.
  - `tests/test_sandbox.py`: 5 comprehensive tests validating stack detection, test execution, environment secret scrubbing, timeout termination, and CLI JSON output.

### Verification & Measured Results
- `pytest tests/test_sandbox.py`: 5/5 tests passed in 8.67s.
- `make test`: 24/24 tests passed in 14.06s.
- CLI execution verification:
  ```json
  {
    "exit_code": 0,
    "duration_ms": 1369.09,
    "timed_out": false,
    "tests": [
      { "name": "test_add", "status": "PASS", "file": "test_calc.py" },
      { "name": "test_subtract", "status": "PASS", "file": "test_calc.py" },
      { "name": "test_multiply", "status": "PASS", "file": "test_calc.py" }
    ]
  }
  ```

### Next Step
Begin Phase 3 verification core implementation.

---

## [Phase 3: Verification Core (Slice 1)] - 2026-10-26

### What Was Built
- **Intent Extraction (`apps/api/receipt_api/verify/intent.py`)**:
  - LLM structured extraction of discrete acceptance criteria with deterministic fallback parsing.
  - Classifies change kind (`bugfix`, `feature`, `refactor`) and testability.
- **Targeted Test Generation (`apps/api/receipt_api/verify/testgen.py`)**:
  - Stack-aware proof test generator creating isolated tests in throwaway `receipt_tests/` directory.
  - LLM client with `chat_structured_sync` supporting synchronous pipeline callers.
- **Fail-Before / Pass-After Proof Engine (`apps/api/receipt_api/verify/failbefore.py`)**:
  - Evaluates candidate tests against `base_sha` and `head_sha`.
  - Vacuous test detection: tests passing on base for bugfix/feature are flagged `vacuous: true` and excluded from proofs.
- **Scoring & Hard Gates (`apps/api/receipt_api/verify/scoring.py`)**:
  - Transparent line-item score calculation with weighted components (behavior 0.35, constraints 0.25, test_strength 0.20, regression 0.15, browser 0.05).
  - Hard gates enforcement: regressions cap verdict at `REJECTED`, blocking constraints and bugfixes with zero non-vacuous proofs cap at `NEEDS_REVIEW` (score <= 69).
- **Receipt Minting & Markdown (`apps/api/receipt_api/verify/receipt.py`)**:
  - `build_receipt`: Assembles validated Pydantic `Receipt` model matching contract fixtures.
  - `format_receipt_markdown`: Formats an ASCII verification receipt for GitHub comments and CLI.
- **Verification Pipeline (`apps/api/receipt_api/verify/pipeline.py`)**:
  - End-to-end orchestration emitting SSE events (`run.started`, `run.step.started`, `run.step.finished`, `run.proof`, `run.score`, `run.finished`).
  - Automatically persists receipts and events into SQLite database with full query capabilities in `main.py`.

### Verification & Measured Results
- `pytest tests/test_verification.py`: 9/9 tests passed in 9.83s.
- `make test`: 33/33 total tests passed in 27.15s across all subsystems.
- `make demo-smoke`: End-to-end smoke check passed with full 5-stage verification receipt output.
- All 6 hard gate conditions verified via parametrized unit tests.

### Next Step
Begin Phase 4 GitHub ingestion implementation.

---

## [Phase 4: GitHub Ingestion (Backfill & Webhooks)] - 2026-10-26

### What Was Built
- **GitHub Client (`apps/api/receipt_api/github/client.py`)**:
  - `GitHubClient` using `httpx.AsyncClient` with ETag conditional caching (`If-None-Match`), 304 handling, pagination support (`get_paginated`), and automatic exponential backoff on secondary rate limits.
- **Repository Ingestion Engine (`apps/api/receipt_api/github/ingest.py`)**:
  - `ingest_from_snapshot`: Parses offline `snapshot.json` containing PRs, review discussions, comments, revert commits, and incident issues.
  - Idempotent event persistence in `GHEvent` table (`pr`, `review`, `review_comment`, `revert`, `incident` kinds) with duplicate deduplication.
  - Emits real-time `ingest.progress` events and updates `Repo.last_ingested_at`.
  - Live GitHub API backfill fallback when credentials are provided.
- **Webhook Receiver (`apps/api/receipt_api/github/webhooks.py`)**:
  - HMAC SHA-256 signature verification (`verify_github_signature`) guarding against unauthorized payloads.
  - Event dispatcher (`handle_webhook_event`) parsing `pull_request` (opened, synchronize, reopened) payloads, persisting `DBRun` in `pending` state, and emitting `run.enqueued` events.
- **REST Endpoints (`main.py`)**:
  - `POST /repos/{id}/ingest`: Ingests history with snapshot override support.
  - `POST /webhooks/github`: Authenticates HMAC header, dispatches events, and enqueues runs.

### Verification & Measured Results
- `pytest tests/test_github_ingest.py`: 4/4 tests passed in 3.06s.
  - Snapshot ingestion: 100% of PRs, reviews, and comments ingested; second run added 0 duplicates (100% idempotent).
  - HMAC SHA-256 verification: valid signature accepted, forged/missing rejected with 401.
  - Webhook pull request trigger: `Run` successfully persisted in database with `run.enqueued` event.
- `make test`: 37/37 tests passed in 31.52s.

### Next Step
Phase 5 (Scar Tissue: Extract lessons, cluster, confidence score, FTS5 + embeddings hybrid retrieval).





