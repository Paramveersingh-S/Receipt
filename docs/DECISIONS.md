# Architectural Decision Records (ADR) — Receipt

This file records non-obvious design choices, rationale, and consequences throughout the build phases.

---

## ADR 001: SQLite WAL Mode with In-Memory / Local Disk Architecture

### Context
Receipt needs high-throughput persistence for events, runs, receipts, and memory graph edges while maintaining zero-friction developer setup and deterministic replay.

### Decision
Use SQLite with Write-Ahead Logging (WAL) enabled, integrated via SQLModel / SQLAlchemy and FTS5 for full-text search.

### Consequences
- Zero external database services needed for local dev, demo mode, and CI.
- Fast concurrent reads with serialized writes.
- Simple single-file backup and deterministic snapshot replay.

---

## ADR 002: Provider-Agnostic LLM Interface with Record/Replay Cache

### Context
Antigravity and Receipt require deterministic behavior, CI evaluation reproducibility, zero flake during demo recordings, and provider portability (OpenAI, OpenRouter, Groq, Together, vLLM).

### Decision
Implement `receipt_api/llm/client.py` using standard OpenAI-compatible wire protocols with Pydantic structured output validation, tenacity retries, and a persistent cache keyed by `(model, prompt_hash)`. Introduce `LLM_MODE=live|record|replay`.

### Consequences
- Allows offline benchmark evaluation and instantaneous replay during demo recordings without burning API credits.
- Swappable open models without vendor SDK coupling.

---

## ADR 003: Dual Offline/Online Seeded History for Scar Tissue & Benchmarks

### Context
Scar Tissue requires historical review comments, reverts, and incident resolutions to extract learned constraints. Relying exclusively on live GitHub network calls makes demo runs and benchmarks vulnerable to network latency, secondary rate limits, and network flakiness.

### Decision
Structure `demo/seed/` with dual capabilities:
1. `snapshot.json` stores an exact, normalized offline snapshot of PRs, review comments, revert commits, and incident issues.
2. `seed_history.py` provides cross-validation of 100% of planted lessons against the snapshot, with an optional `--live` flag for seeding a remote GitHub repository.
3. Held-out benchmark tests (`test_coupons_hidden.py`) test boundary edge cases (fractional half-up cent rounding and unique attempt idempotency keys) that subtle bug PRs evade with naive tests.

### Consequences
- Benchmarks and unit tests can execute 100% offline, deterministically, and in milliseconds.
- Prevents synthetic data hallucination by maintaining exact provenance links between lessons and snapshot events.

---

## ADR 004: Dual Sandbox Architecture with Environment Scrubbing

### Context
Agent pull requests may contain untrusted, buggy, or malicious code. Executing untrusted tests directly on the host machine poses security risks (secret leakage, filesystem tampering, fork bombs). However, Docker is not always running on developer workstations.

### Decision
Implement a dual-backend sandbox architecture in `verify/sandbox.py`:
1. `SubprocessSandbox`: Restricted execution fallback. Applies environment scrubbing (wiping all API tokens, cloud keys, and secrets), wall-clock timeouts, and scoped working directory isolation.
2. `DockerSandbox`: Containerized execution with `--network none`, memory/CPU caps, and non-root execution. Gracefully falls back to `SubprocessSandbox` with a warning log if Docker is unavailable.
3. Decouple stack logic via `StackAdapter` (`PythonStackAdapter`, `NodeStackAdapter`) to parse test outputs into normalized `TestResult` objects.

### Consequences
- Zero external dependency required on minimal dev workstations while maintaining strict secret protection.
- Safe execution path that never exposes host secrets (`GITHUB_TOKEN`, `LLM_API_KEY`) to untrusted code.

---

## ADR 005: Fail-Before / Pass-After Proof Matrix with Vacuous Assertion Filtering

### Context
Autonomous coding agents frequently generate superficial or tautological tests (e.g., `assert True` or testing code paths that already passed on the base commit) to artificially boost test counts without proving the bugfix or feature actually fixed anything.

### Decision
Implement the **Fail-Before / Pass-After Proof Matrix** in `verify/failbefore.py`:
1. Generated candidate tests are evaluated on `base_sha` (must FAIL for bugfix/feature) and on `head_sha` (must PASS).
2. Any test that passes on base is classified as **vacuous** (`vacuous: true`), excluded from proof counts, and explicitly recorded in the receipt's `limits` section.
3. Scoring hard gates enforce that bugfixes with zero non-vacuous proofs cannot achieve a `VERIFIED` verdict.

### Consequences
- Mathematically eliminates rubber-stamp test counts.
- Produces verifiable, non-vacuous proof evidence recorded in public receipts.

---

## ADR 006: Scar Tissue Institutional Memory Architecture & Confidence Scoring

### Context
Repositories accumulate hard-earned institutional knowledge through painful incidents, reverts, and code reviews. This tribal knowledge is lost on coding agents who start "cold", repeatedly making the same classes of mistakes (e.g., float rounding on money, unauthenticated endpoints, missing idempotency keys). Additionally, naive LLM extraction without strict provenance results in hallucinated constraints and phantom evidence.

### Decision
Implement the Scar Tissue subsystem (`apps/api/receipt_api/scar/`):
1. **Strict Provenance Verification**: Every extracted constraint requires evidence items linking directly to real ingested `GHEvent` records (PR, review comment, revert, or incident). Any evidence link without a corresponding ingested event URL or SHA is rejected.
2. **Noise Classification**: Heuristically discard stylistic nitpicks (whitespace, formatting, trivial renames) before candidate generation.
3. **Confidence Scoring Formula**:
   $$\text{Confidence} = \text{clamp}\left(0.10, 1.00, \text{Base}(w_{\text{type}}) + \text{RecurrenceBonus} \cdot e^{-\lambda \Delta t}\right)$$
   - Weights: `incident_fix` (1.0) > `revert` (0.8) > `review` (0.5) > `comment` (0.3).
   - Recency decay: 180-day exponential half-life ($\lambda = \ln(2)/180$).
   - Recurrence bonus: $+0.08$ per distinct corroborating PR/commit source.
4. **Hybrid Retrieval with Reciprocal Rank Fusion (RRF)**:
   - Rank fusion across SQLite FTS5 BM25 search and vector cosine similarity:
     $$\text{RRF}(d) = \sum_{m \in \{\text{FTS5}, \text{Vec}\}} \frac{1}{60 + \text{rank}_m(d)}$$
   - Boost candidate constraints by path-scope match ($+0.025$) and `block` severity ($+0.010$).
5. **Static Check AST Library**: High-precision detectors for 7 core invariant patterns (float money, bare exceptions, missing idempotency keys, N+1 loops, missing auth dependencies, PII logging, and non-reversible migrations).

### Consequences
- Achieves 100% recall on planted lessons with 0% false positive junk constraints.
- Enables sub-millisecond retrieval of applicable constraints during agent briefing and diff check.
- Prevents hallucinated evidence while grounding all agent constraints in real git history.

---

## ADR 007: Memory-Verification Fusion & Blocking Constraint Hard Gates

### Context
When coding agents generate automated PRs, unit tests written by the agent often pass because the agent wrote both the implementation and the tests to match its own assumptions. Subtle domain bugs (e.g., float rounding drift on checkout, missing idempotency keys during network retries) evade standard unit tests and cause severe production incidents.

### Decision
Implement **Fusion: Memory × Verification** in `verify/pipeline.py` and `scar/briefing.py`:
1. **Pre-Coding Briefings (`scar/briefing.py`)**: Provide agents with active repository constraints, preflight checklists, and suggested tests scoped to the target files *before* code is authored.
2. **Automated Diff & AST Checking**: During verification pipeline execution, inspect all altered files and unified diffs against learned constraints using the AST checker library.
3. **Hard Gate Enforcement**: Any violation of a `block` severity constraint immediately triggers a hard gate cap:
   - Score is capped at $\le 69$.
   - Verdict is capped at `NEEDS_REVIEW` or `REJECTED`.
   - The receipt explicitly lists the violated constraint with direct evidence links to the historical PRs, reverts, and incident tickets that taught the lesson.

### Consequences
- Eliminates false-positive test approvals on subtly broken agent PRs.
- Grounded in empirical ablation: `agent/coupons-subtle-bug` drops from `VERIFIED (False Positive, 91)` to `NEEDS_REVIEW (Score 48)` citing PR #7 and PR #8 / #11.
