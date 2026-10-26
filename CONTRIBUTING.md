# Contributing to Receipt

We welcome contributions to **Receipt: Verification + Institutional Memory for Agent-Written Code**.

---

## 🏛️ Development Philosophy

1. **Contract-First:** Contracts in `contracts/` (`openapi.json`, `events.schema.json`, `fixtures/*.json`) are the ground truth. Any API or schema change must update fixtures and `docs/CONTRACT_CHANGELOG.md`.
2. **Zero-Trust Sandboxing:** Untrusted agent code never executes directly on the host. Always execute test suites via `SubprocessSandbox` or `DockerSandbox` with network disabled.
3. **Institutional Memory Grounding:** Evidence citations must link to real GitHub PRs, commits, and comments ingested into the repository. Never fabricate rules or citations.
4. **Targeted Mutation Testing:** Test changes with AST mutations on altered line ranges (`verify/mutation/`) to measure true test strength.

---

## 🛠️ Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/Paramveersingh-S/Receipt.git
cd Receipt

# 2. Setup environment
cp .env.example .env

# 3. Run all tests
make test

# 4. Run demo smoke test
make demo-smoke

# 5. Run benchmark harness
make bench
```

---

## 🧪 Testing Standards

- Every PR must end with passing tests: `pytest tests/ -v`.
- Strict typing and linting must pass: `ruff check` and `mypy`.
- Conventional commit messages are required (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Document design decisions in `docs/DECISIONS.md` (ADR format) and log milestones in `docs/BUILD_LOG.md`.
