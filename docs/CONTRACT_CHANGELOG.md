# Contract Changelog

All modifications to `contracts/openapi.json`, `contracts/events.schema.json`, or `contracts/fixtures/*.json` must be logged here to coordinate with the UI track.

---

## 2026-10-26 — Initial Contract Baseline (v0.1.0)
- Defined initial OpenAPI REST specifications for `/repos`, `/runs`, `/receipts`, `/constraints`, `/bench`, `/health`, and SSE event stream endpoints.
- Established event schemas for SSE event replay.
- Created standard fixtures for verified, rejected, and needs_review receipts, constraints, run events, and graph connections.
