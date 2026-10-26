<div align="center">

# 🧾 RECEIPT

### **Verification + Institutional Memory for Autonomous Agent PRs**

[![Backend CI](https://img.shields.io/badge/backend%20tests-65%20passed-10b981?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/Paramveersingh-S/Receipt)
[![Frontend UI](https://img.shields.io/badge/frontend-Next.js%2016%20Turbopack-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://github.com/Paramveersingh-S/Receipt)
[![Line Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen?style=for-the-badge&logo=codecov&logoColor=white)](https://github.com/Paramveersingh-S/Receipt)
[![Python 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/Paramveersingh-S/Receipt)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP%20v1.0%2B-8B5CF6?style=for-the-badge&logo=anthropic&logoColor=white)](https://github.com/Paramveersingh-S/Receipt)
[![Contracts](https://img.shields.io/badge/contracts-OpenAPI%20%2B%20SSE-blueviolet?style=for-the-badge)](https://github.com/Paramveersingh-S/Receipt)
[![License](https://img.shields.io/badge/license-Apache--2.0-F59E0B?style=for-the-badge)](https://github.com/Paramveersingh-S/Receipt)

<p align="center">
  <a href="#-executive-summary">Executive Summary</a> •
  <a href="#-system-architecture">Architecture</a> •
  <a href="#-step-by-step-verification-lifecycle">Lifecycle (Steps 1–9)</a> •
  <a href="#-macos-grade-web-interface">Web Dashboard</a> •
  <a href="#-the-evidence-receipt">The Receipt</a> •
  <a href="#-empirical-benchmarks">Benchmarks</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-security-sandbox">Security</a>
</p>

---

</div>

## 💡 Executive Summary

Autonomous coding agents (Claude Code, Cursor, Codex, Devin) write code at superhuman speed, but code review is breaking down:

1. **Rubber-stamping crisis**: Human engineers become bottlenecks reading hundreds of agent diff lines daily.
2. **Superficial "happy-path" tests**: Agents write tests designed to pass their own buggy code, yielding a false sense of security.
3. **Amnesia on every prompt**: Agents start with zero institutional memory, repeatedly re-introducing the same bugs your team fixed months ago (e.g., float division in pricing, missing idempotency keys on payment retries, unauthenticated endpoints).

**Receipt solves this with two interconnected subsystems:**

- **🧬 Scar Tissue (Institutional Memory)**: Automatically extracts architectural constraints from repository history (reverts, incident hotfixes, and review comments), clusters them into rules with real provenance links, and serves them to agents over FastMCP *before* they edit files.
- **⚡ Receipt (Verification Engine)**: Evaluates agent PRs in an isolated sandbox with **fail-before / pass-after proofs**, AST-level **mutation testing on changed lines**, regression checks, and browser QA — then loops failure diagnostics back for autonomous self-healing.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
  subgraph GITHUB ["External Version Control & Developer Agents"]
    REPO["GitHub Repository<br/>PRs • Review Comments • Reverts • Incident Hotfixes"]
    AGENTS["Coding Agents<br/>Claude Code • Cursor • Codex • Devin"]
  end

  subgraph MEMORY ["Subsystem 1: Scar Tissue (Institutional Memory)"]
    INGEST["Repo Ingestion Engine<br/>Extracts Lessons from Reverts & Comments"]
    CLUST["Constraint Clustering & Scoring<br/>Severity: Block | Warn | Info"]
    STORE[("SQLite Storage<br/>WAL Mode + FTS5 Full-Text Search")]
    MCP["FastMCP Server<br/>get_scar_briefing() • check_diff()"]
  end

  subgraph VERIFY ["Subsystem 2: Receipt Verification Engine"]
    INTENT["1. Intent Extraction<br/>Acceptance Criteria from PR Body"]
    FAILBEFORE["2. Fail-Before Proof Gen<br/>Base = FAIL, Head = PASS"]
    SANDBOX["3. Isolated Sandbox Container<br/>Docker / Bubblewrap (No Network)"]
    MUTATION["4. AST Mutation Testing<br/>Operators on Changed Lines Only"]
    SCAR_CHECK["5. Scar Constraint Check<br/>Diff Invariant Evaluation"]
    BROWSER_QA["6. Headless Browser QA<br/>UI Screenshots & State Verification"]
    REPAIR["7. Auto-Repair Loop<br/>Diagnostic Feedback (Max 3 Turns)"]
    MINT["8. Evidence Receipt Minting<br/>Cryptographic Digest & Score"]
  end

  subgraph OUTPUTS ["Developer & CI Surfaces"]
    UI["macOS-Grade Web Dashboard<br/>Next.js 16 • Framer Motion • Skeuomorphic Card"]
    STATUS["GitHub Checks & PR Comment<br/>Formatted Evidence Receipt"]
  end

  REPO -->|1. Ingest History| INGEST --> CLUST --> STORE
  STORE <--> MCP
  AGENTS <-->|2. Pre-flight Briefing| MCP
  AGENTS -->|3. Open Pull Request| REPO
  REPO -->|4. Webhook Trigger| INTENT
  INTENT --> FAILBEFORE --> SANDBOX
  SANDBOX --> MUTATION
  STORE -->|Supply Invariants| SCAR_CHECK
  SANDBOX --> SCAR_CHECK
  SANDBOX --> BROWSER_QA
  BROWSER_QA -->|If Fails| REPAIR
  REPAIR -->|Inject Patch| SANDBOX
  BROWSER_QA -->|If Passes| MINT
  MINT --> UI
  MINT --> STATUS
```

---

## 🔄 Step-by-Step Verification Lifecycle

Receipt defines a 9-step closed-loop lifecycle from initial repo ingestion to verified pull request deployment:

### Step 1: Institutional Memory Mining
The `receipt_api/scar/` engine parses past PRs, commits, and review comments. It identifies patterns associated with regressions (e.g. `Revert PR #7: Float rounding drift created penny discrepancies`) and extracts them into structured **Scar Tissue Constraints** with real evidence links.

### Step 2: Pre-Flight FastMCP Briefing
Before an agent edits files, it calls Receipt's FastMCP tool:
```python
briefing = await mcp.get_scar_briefing(paths=["shop/pricing.py"])
```
The agent receives active constraints with their historical reasoning and exact rules (e.g., *Rule: Represent and compute all money as integer cents*), preventing errors before code is even written.

### Step 3: Webhook Ingestion & Intent Analysis
When an agent submits a pull request, Receipt's webhook listener (`github/webhooks.py`) ingests the payload, records base and head commit SHAs, and extracts discrete, testable acceptance criteria using structured LLM analysis (`verify/intent.py`).

### Step 4: Fail-Before / Pass-After Proof Matrix
To ensure tests aren't tautological no-ops:
1. Receipt generates candidate tests for each acceptance criterion (`verify/testgen.py`).
2. Tests are executed against the **base commit** in an isolated container. They **MUST FAIL**.
3. Tests are executed against the **head commit**. They **MUST PASS**.
4. Any test that passes on base is marked **vacuous** and rejected as proof.

### Step 5: AST Mutation Scoring on Changed Lines
Standard code coverage is easily gamed. Receipt performs **AST-level mutation testing** (`verify/mutation/`) strictly on modified lines:
- Mutants: Invert comparisons (`>` ➔ `>=`), swap arithmetic (`+` ➔ `-`), flip booleans, remove function calls.
- Scoring: If tests do not kill these mutants, the PR's mutation score drops and verification flags survivors.

### Step 6: Scar Constraint Enforcement
The pull request diff is evaluated against active Scar Tissue constraints. Any violation of a `block`-level invariant triggers an immediate failure with an explanation of why the rule exists and citations to past incidents.

### Step 7: Headless Browser QA (Visual State Verification)
For UI and full-stack pull requests, Receipt boots the application in a sandboxed headless browser (`verify/browserqa.py`), executes critical user interactions (e.g. applying a coupon code in the cart), and captures screenshot artifacts.

### Step 8: Closed-Loop Auto-Repair
If verification fails (e.g., float math used or a mutation survived), Receipt enters the **repair loop** (`repair/loop.py`):
1. Aggregates failure traces, violated constraints, and survivor diffs into a structured diagnostic prompt.
2. Injects the prompt into the LLM or external agent CLI.
3. Applies candidate patches in-place and re-executes verification.
4. Bounded to a maximum of 3 iterations with strict timeouts to prevent runaway loops.

### Step 9: Digital Evidence Receipt Minting
When verification succeeds (or terminates), Receipt compiles all proof matrices, mutation scores, regression logs, and constraint audits into a **signed evidence receipt** (`verify/receipt.py`), updates GitHub commit statuses, and publishes the interactive receipt.

---

## 🖥️ macOS-Grade Web Interface

The frontend (`apps/web`) is a desktop-grade web application built with **Next.js 16 (App Router)**, **TypeScript**, **Tailwind CSS v4**, and **Framer Motion**:

| Surface | Key Capabilities |
|---|---|
| **macOS Window Frame** | Functional traffic lights, active repo breadcrumbs, live SSE status pill, quick PR switcher (PR #12 Verified vs PR #13 Buggy). |
| **Skeuomorphic Receipt Card** | Perforated sawtooth edges, thermal monospace font, rubber stamp verdict (`[VERIFIED]` / `[REJECTED]`), SVG barcode, cryptographic digest, and confetti on copy. |
| **Live Pipeline Stream** | Real-time 7-stage visual timeline, animated stage nodes, and filterable live SSE event terminal stream (`/runs/{id}/events`). |
| **Scar Tissue Graph** | Interactive knowledge graph connecting constraints, scoped files, historical PRs, reverts, and incidents with a sliding slide-out inspector. |
| **Auto-Repair Inspector** | Multi-turn score convergence curve (+40 pts recovered), diagnostic feedback inspector, and side-by-side colorized code diffs. |
| **ReceiptBench Dashboard** | Empirical comparison bar charts comparing Baseline A, Baseline B, Ablated Receipt, and Full Receipt across recall, precision, and repair success. |
| **Command Palette (`⌘K`)** | Global keyboard shortcut dialog for instant navigation across views, PR switching, and receipt extraction. |

---

## 🧾 The Verification Receipt

```text
======================================================================
 RECEIPT // VERIFICATION EVIDENCE RECORD
======================================================================
 Repository   : Paramveersingh-S/receipt-demo-shop
 Pull Request : #12 - "feat: Add coupon discount support at checkout"
 Author       : agent/claude-code
 Public Slug  : x7k2m9 (http://localhost:3000/r/x7k2m9)
 Verdict      : [VERIFIED] (Trust Score: 92/100)
 Duration     : 142.1s • 2 iterations (Repaired in Iteration 1)
----------------------------------------------------------------------
 [01] ACCEPTANCE PROOFS (Fail-Before / Pass-After)
  [ac1] test_coupon_rounds_half_up         Base: FAIL -> Head: PASS  [Valid]
  [ac2] test_expired_coupon_returns_400     Base: FAIL -> Head: PASS  [Valid]
  [ac3] test_checkout_idempotency_key       Base: FAIL -> Head: PASS  [Valid]
  Result: 3/3 Criteria Proven (0 Vacuous)

 [02] REGRESSION SUITE CHECK
  Base Commit : 41 passed, 0 failed
  Head Commit : 44 passed, 0 failed
  Regressions : 0 DETECTED (Clean Suite)

 [03] AST MUTATION SCORE ON CHANGED LINES
  Score: 89.0% (32 killed / 4 survived / 36 total)
  Survivors: 4 (inspected in shop/pricing.py:48)

 [04] SCAR TISSUE CONSTRAINTS ENFORCED
  [PASS] sc_001: Money is integer cents, never float (Incident #7, PR #8)
  [PASS] sc_002: Payment retry calls require idempotency key (PR #11)
  Result: 2/2 Enforced, 0 Violations

 [05] VISUAL BROWSER QA
  [PASS] Apply coupon at checkout updates cart total UI
  [PASS] Invalid coupon renders inline error banner
  Artifacts: 2 Screenshots Stored (ar_shot_1, ar_shot_2)
----------------------------------------------------------------------
 SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
 ★ VERIFIED AUTONOMOUSLY BY RECEIPT ★
======================================================================
```

---

## 📊 Empirical Benchmarks

Evaluated across **ReceiptBench** (24 diverse evaluation tasks with planted subtle bugs and regressions across 3 repositories) and **ScarBench** (institutional lesson recovery):

```text
Defect Detection Rate (Recall)
Baseline A (PR Tests Only)    [==                                      ]  8.3%
Baseline B (LLM Diff Review)  [=====================                   ] 54.2%
Receipt (No Scar Tissue)      [===============================         ] 79.2%
Receipt (Full System)         [======================================  ] 95.8%

Autonomous Repair Success Rate
Baseline A (PR Tests Only)    [                                        ]  0.0%
Baseline B (LLM Diff Review)  [                                        ]  0.0%
Receipt (No Scar Tissue)      [==========================              ] 66.7%
Receipt (Full System)         [====================================    ] 91.7%
```

### Detailed Comparative Metrics (ReceiptBench)

| System Evaluated | Defect Recall | False Positive Rate | Precision | F1 Score | Mean Latency | LLM Cost | Repair Success |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A** (PR's own tests) | 8.3% | **0.0%** | 100.0% | 0.15 | **18.4s** | **$0.000** | 0.0% |
| **Baseline B** (LLM diff review) | 54.2% | 25.0% | 68.4% | 0.60 | 32.1s | $0.034 | 0.0% |
| **Receipt (Ablated: No Scar)** | 79.2% | 8.3% | 90.5% | 0.85 | 128.0s | $0.082 | 66.7% |
| **Receipt (Full System)** | **95.8%** | 4.2% | **95.8%** | **0.96** | 142.5s | $0.098 | **91.7%** |

### ScarBench Institutional Memory Audit

| Evaluation Metric | Measured Value | Target Standard | Evaluation Status |
| :--- | :---: | :---: | :--- |
| **Planted Lesson Recall** | `7/7 (100%)` | 100% | 🟢 Perfect Recall |
| **Extraction Precision** | `88.0%` | >= 80% | 🟢 High Signal |
| **Recall @ 1 (Top-1 Relevance)** | `85.7%` | >= 75% | 🟢 Accurate Retrieval |
| **Recall @ 3 (Top-3 Coverage)** | `100.0%` | >= 90% | 🟢 Complete Invariant Coverage |
| **Maintainer Agreement Audit** | `28/30 (93.3%)` | >= 90% | 🟢 Grounded in Real Regressions |
| **False Positive Noise Rate** | `6.7%` | <= 10% | 🟢 Minimal Noise |

### Memory Ablation Study

| Configuration | Defect Recall | Precision | F1 Score | Regressions Prevented | Repair Recovery |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Without Memory (Ablation: No Scar Tissue)** | 79.2% | 90.5% | 0.85 | 0% (Blind to historical conventions) | 66.7% |
| **With Memory (Receipt Full System)** | **95.8%** | **95.8%** | **0.96** | **100% (7/7 historical invariants blocked)** | **91.7%** |

### Verified Test Suite Breakdown (65/65 Passed)

| Subsystem & Test Suite | Test Location | Test Count | Scope of Verification | Status |
| :--- | :--- | :---: | :--- | :---: |
| **REST & Contracts** | `tests/test_contracts.py` | 7 | OpenAPI 3.1 schema & 11 contract fixtures | ✅ Passed |
| **SSE Event Stream** | `tests/test_events.py` | 3 | Append-only event log & historical replay | ✅ Passed |
| **Background Jobs** | `tests/test_jobs.py` | 2 | SQLite persistent job queue & retry worker | ✅ Passed |
| **LLM Interface** | `tests/test_llm.py` | 2 | Deterministic caching & record/replay engine | ✅ Passed |
| **Database & FTS5** | `tests/test_models.py` | 2 | SQLite WAL mode & BM25 full-text indexing | ✅ Passed |
| **Sandbox Isolation** | `tests/test_sandbox.py` | 5 | Subprocess, Docker, env scrubbing, timeouts | ✅ Passed |
| **Verification Core** | `tests/test_verification.py` | 9 | Fail-before proofs & scoring hard gates | ✅ Passed |
| **GitHub Ingestion** | `tests/test_github_ingest.py` | 4 | Snapshot replay & HMAC-SHA256 webhooks | ✅ Passed |
| **Scar Tissue Memory** | `tests/test_scar.py` | 5 | Extraction, clustering & hybrid RRF search | ✅ Passed |
| **Memory × Verify Fusion** | `tests/test_fusion.py` | 3 | Pre-flight briefing & constraint hard gates | ✅ Passed |
| **AST Mutation Engine** | `tests/test_mutation.py` | 3 | AST operators on changed lines only | ✅ Passed |
| **Browser Visual QA** | `tests/test_browserqa.py` | 2 | End-to-end checkout & screenshot diffs | ✅ Passed |
| **Closed-Loop Auto-Repair** | `tests/test_repair.py` | 3 | Multi-turn repair loop & patch guardrails | ✅ Passed |
| **Ecosystem Integrations** | `tests/test_integrations.py` | 5 | FastMCP tools, living docs & learning loop | ✅ Passed |
| **Evaluation Harness** | `tests/test_bench.py` | 4 | ReceiptBench & ScarBench evaluators | ✅ Passed |
| **Security Hardening** | `tests/test_security.py` | 3 | Secret scrubbing & prompt injection defense | ✅ Passed |
| **Target Demo App** | `tests/fixtures/.../test_calc.py` | 3 | Baseline calculator reference test suite | ✅ Passed |
| **TOTAL VERIFIED SUITE** | **17 test suites** | **65** | **Zero failures across all 11 phases** | **100% GREEN** |

---

## 🚀 Step-by-Step Demo & Getting Started Guide

Follow these simple steps to explore the live demo, run the interactive CLI, or boot the full-stack system.

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** & **pnpm** (`npm install -g pnpm`)
- **Git**

### Step 1: Clone & Configure

```bash
# Clone the repository
git clone https://github.com/Paramveersingh-S/Receipt.git
cd Receipt

# Copy example environment configuration
cp .env.example .env

# Set up Python virtual environment and install backend dependencies in editable mode
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# On Linux / macOS:
# source .venv/bin/activate && pip install -e ".[dev]"

# Install frontend dependencies
cd apps/web
pnpm install
cd ../..
```

---

### Step 2: Run the 1-Click Interactive CLI Demo

The quickest way to experience the entire Receipt lifecycle in action:

```bash
make demo
# Or directly with Python:
python -m receipt_api.demo_runner
```

**What this demonstrates in your terminal:**
1. **Zero-Dependency Persistence**: Initializes SQLite WAL database and FTS5 search index.
2. **Institutional Memory Retrieval**: Displays 15 active learned constraints extracted from past repo incidents.
3. **FastMCP Pre-Flight Briefing**: Demonstrates how Claude Code or Cursor queries constraints before touching `shop/pricing.py`.
4. **Multi-Stage Verification Gate (PR #12)**:
   - Executes acceptance proofs (`Base: FAIL -> Head: PASS`).
   - Runs 36 mutant operators via AST mutation testing (89% killed).
   - Validates Scar Tissue invariant compliance (integer cents, idempotency keys).
   - Simulates visual headless browser QA with screenshot artifacts.
5. **Closed-Loop Auto-Repair (PR #13)**:
   - Detects float division bug on buggy PR #13.
   - Diagnoses constraint violation and synthesizes integer cents patch.
   - Re-verifies in sandbox and recovers score from 52 to 90+ in a single turn.
6. **Digital Receipt Minting**: Prints the cryptographic receipt with trust score, breakdown, and SHA-256 digest.

---

### Step 3: Run the macOS Desktop Web Interface

Experience the developer desktop interface with animations, live SSE timeline, and skeuomorphic receipt card:

```bash
cd apps/web
pnpm dev
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

**Features to try in the web UI:**
- **Skeuomorphic Receipt Card**: Observe the thermal printer styling, perforated jagged edges, rubber-stamped verdict badge, and SVG barcode.
- **Confetti on Copy**: Click the **"Copy Digest"** button on the receipt to trigger celebratory canvas confetti!
- **PR Switcher**: Click the PR selector in the macOS titlebar to switch between **PR #12 (Verified)** and **PR #13 (Buggy)** to compare proof results side-by-side.
- **Live 7-Stage Pipeline Visualizer**: View stage-by-stage execution with pulsing status pills and live terminal SSE event streaming (`/runs/{id}/events`).
- **Interactive Scar Tissue Knowledge Graph**: Explore rules, affected files, historical PRs, reverts, and incident hotfixes with slide-out details.
- **Auto-Repair Inspector**: Track the score recovery curve and review colorized before/after code diffs.
- **ReceiptBench Dashboard**: Examine empirical bar charts comparing detection rates and repair success.
- **Command Palette (`⌘K` / `Ctrl+K`)**: Use the global keyboard shortcut to jump instantly between views.

---

### Step 4: Run the Backend API & Interactive OpenAPI Docs

Start the FastAPI backend with live reload:

```bash
make dev
# Or directly:
uvicorn receipt_api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api
```

- **Interactive Swagger Docs**: **[http://localhost:8000/docs](http://localhost:8000/docs)**
- **ReDoc Documentation**: **[http://localhost:8000/redoc](http://localhost:8000/redoc)**
- **Health Check**: `curl http://localhost:8000/health`
- **Active Constraints**: `curl http://localhost:8000/repos/repo_demo_shop/constraints`
- **Verification Receipt**: `curl http://localhost:8000/receipts/rc_01JJ88F4R00000000000000001`

---

### Step 5: Run the Benchmark Replication Harness

Reproduce the empirical numbers from the benchmark report:

```bash
make bench
# Or directly:
python -m bench.runner
```

Runs 24 stratified pull request tasks across `receipt-demo-shop`, `tiny-ledger`, and `mini-url-service`, evaluating recall, precision, false positive rate, latency, and autonomous repair recovery.

---

### Step 6: Run the Full Test Suite

Run all 65 automated tests verifying every subsystem:

```bash
make test
# Or directly:
pytest tests -v
```

---

### Step 7: Connect External Coding Agents via FastMCP

Receipt exposes institutional memory and verification tools to **Claude Code**, **Cursor**, **Codex**, and **Devin**:

```bash
# Inspect and run FastMCP tools interactively
npx @modelcontextprotocol/inspector python mcp_server.py
```

**Tools available to coding agents:**
- `receipt_briefing(repo, task, paths)`: Pre-coding institutional constraints checklist.
- `receipt_check_diff(repo, diff)`: Instant AST invariant checking on staged diffs.
- `receipt_verify_pr(repo, pr_number)`: Triggers isolated sandbox verification.
- `receipt_get_receipt(receipt_id)`: Fetches digital evidence receipt.
- `scar_search(query, repo)`: Hybrid BM25 + cosine vector search over institutional memory.
- `scar://constraints/{path}`: FastMCP URI resource providing constraints scoped to a specific file.

---

## 🛡️ Security Sandbox

Receipt is architected under the **Hostile Code Assumption**: all agent-generated code and third-party pull requests are treated as untrusted and potentially malicious.

1. **Containment**: Untrusted code never executes directly on the developer host. All test runs, mutation probes, and proof executions run inside hardened containers (Docker or Bubblewrap).
2. **Network Isolation**: The execution step operates with **network access completely disabled** (`--network none`). No secrets, environment tokens, or host keys are ever mounted into the container.
3. **Resource Capping**: Strict memory (2GB), CPU (2 cores), and PID (128 processes) limits prevent fork bombs and denial-of-service loops.
4. **Prompt Injection Hardening**: All PR diffs, review comments, and issue descriptions are treated strictly as data enclosed in delimiter boundaries. Hard gates cannot be bypassed by natural language prompts.

---

## 📁 Repository Structure

```text
receipt/
├── AGENTS.md                  # Team mission, rules, and non-negotiables
├── Makefile                   # Automation targets (dev, test, lint, mock, demo)
├── contracts/                 # Contract-first schemas & fixtures
│   ├── openapi.json           # 24-endpoint OpenAPI specification
│   ├── events.schema.json     # Replay-capable SSE schema
│   └── fixtures/              # Mock receipts, constraints, and graphs
├── apps/
│   ├── api/receipt_api/       # Backend FastAPI engine
│   │   ├── main.py            # Primary REST & SSE router
│   │   ├── db.py              # SQLite WAL + FTS5 database layer
│   │   ├── models.py          # SQLModel tables (repos, runs, constraints)
│   │   ├── events.py          # SSE event bus with persistent replay
│   │   ├── jobs.py            # SQLite persistent background job queue
│   │   ├── llm/               # Provider-agnostic LLM client & structured outputs
│   │   ├── scar/              # Scar Tissue: extract, cluster, score, retrieve
│   │   ├── verify/            # Sandbox pipeline, mutation scoring, proofs
│   │   └── repair/            # Closed-loop self-healing repair engine
│   └── web/                   # macOS-Grade Next.js 16 Web Dashboard
│       ├── src/app/           # App router (layout, globals.css, page)
│       ├── src/components/    # MacTitlebar, MacDock, ReceiptCard, etc.
│       ├── src/lib/           # Offline fixture registry & SSE client
│       └── src/types/         # Contract TypeScript interfaces
├── demo/
│   ├── demo-shop/             # TipJar Shop target repository
│   └── seed/                  # Seeding engine, snapshot.json, hidden tests
└── tests/                     # Comprehensive test suites
```

---

<div align="center">
  <sub>Built with ❤️ for autonomous engineering • <b>Receipt: Proof, Not Promises.</b></sub>
</div>
