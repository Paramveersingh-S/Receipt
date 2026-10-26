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
