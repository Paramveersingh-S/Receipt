# AGENTS.md — Receipt

## Mission
Build **Receipt**: verification + memory for agent-written code. Two subsystems that feed each other:
- **Scar Tissue**: learns constraints from repo history (review comments, reverts, incident fixes), serves them to agents via MCP, checks diffs against them.
- **Receipt**: verifies an agent PR in a sandbox (fail-before/pass-after tests, mutation score on changed lines, constraint checks, regression suite, browser QA), loops failures back for repair, outputs an evidence "receipt".

## Non-negotiables
1. Contract-first. `contracts/openapi.json`, `contracts/events.schema.json` and `contracts/fixtures/*.json` are the source of truth. Never change a contract silently; update fixtures and `docs/CONTRACT_CHANGELOG.md`.
2. Every phase ends with passing tests AND the phase's verification commands. Paste real output into your walkthrough. Never claim done without running them.
3. Untrusted code never runs on the host without the sandbox layer (see docs/SECURITY.md). No secrets in the sandbox env. Network off by default in sandboxes.
4. Provider-agnostic LLM calls through `receipt_api/llm/client.py` only. OpenAI-compatible API. Structured outputs validated with Pydantic; retry-with-repair on invalid JSON (max 2). No direct vendor SDK calls elsewhere.
5. Everything has timeouts, resource limits and cancellation. No unbounded loops. Repair loop max 3 iterations. Mutation runs time-boxed.
6. Deterministic by default: seeds, temperature 0–0.2 for extraction/verification, fixed prompts versioned in `receipt_api/prompts/`.
7. Small commits, conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Commit after each green step.
8. After each phase: append to `docs/BUILD_LOG.md` (what/why/tradeoffs/what's next) and add ADRs to `docs/DECISIONS.md` for any non-obvious choice.
9. Honest scope: supported stacks v1 = Python/pytest, Node/vitest|jest. Unsupported repos must fail gracefully with a clear message in the receipt, never crash.
10. Don't invent facts about the repo under test. Evidence links must point to real PRs/commits/comments that exist in the ingested data.

## Stack
- Backend: Python 3.12, `uv`, FastAPI, Pydantic v2, SQLModel/SQLAlchemy, SQLite (WAL) + FTS5, numpy cosine for embeddings, `docker` SDK (optional) / restricted subprocess fallback, `mcp` Python SDK (FastMCP), `httpx`, `tenacity`, `structlog`, `pytest`, `ruff`, `mypy` (strict on `verify/` and `scar/`).
- Frontend (Claude's track): Next.js App Router + TypeScript, Tailwind, shadcn/ui, Framer Motion, TanStack Query, Recharts, React Flow, cmdk, sonner.
- Tooling: `make dev`, `make test`, `make lint`, `make bench`, `make demo`.

## Repo layout
```
receipt/
  AGENTS.md  README.md  Makefile  docker-compose.yml  .env.example
  .agent/rules/  .agent/workflows/
  docs/  ARCHITECTURE.md DECISIONS.md BUILD_LOG.md SECURITY.md CONTRACT_CHANGELOG.md ALAN_INTEGRATION.md
  contracts/  openapi.json  events.schema.json  fixtures/
  apps/api/receipt_api/
      main.py config.py db.py models.py schemas.py events.py jobs.py
      llm/        client.py structured.py embeddings.py providers/
      prompts/    *.md (versioned)
      github/     client.py webhooks.py ingest.py statuses.py
      scar/       extract.py cluster.py score.py store.py retrieve.py briefing.py checks.py docs_gen.py
      verify/     pipeline.py intent.py sandbox.py testgen.py failbefore.py scoring.py receipt.py browserqa.py
                  stacks/{python.py,node.py}  mutation/{python_ast.py,js_tokens.py}
      repair/     loop.py patcher.py external.py
      mcp_server.py
  apps/web/       (Next.js — owned by Claude)
  bench/          scar_eval/ receipt_eval/ results/
  demo/           demo-shop/ seed/
  scripts/
```

## Definition of done (any task)
Code + tests + types + lint pass; contract/fixtures updated if touched; docs/BUILD_LOG.md updated; commit made; walkthrough artifact contains real command output.
