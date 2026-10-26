import datetime
import secrets
import string
from typing import Any, Optional

from receipt_api.schemas import Receipt


def generate_receipt_slug() -> str:
    """Generate a 6-character human-friendly URL slug (e.g. 'x7k2m9')."""
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))


def generate_receipt_id() -> str:
    """Generate a receipt identifier."""
    return f"rc_{secrets.token_hex(12)}"


def build_receipt(
    repo_name: str,
    pr_number: int,
    pr_title: str,
    pr_author: str,
    base_sha: str,
    head_sha: str,
    verdict: str,
    score: int,
    duration_ms: int,
    intent: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    suite: dict[str, Any],
    mutation: dict[str, Any],
    constraints: list[dict[str, Any]],
    browser: dict[str, Any],
    score_breakdown: dict[str, Any],
    limits: list[str],
    iterations: int = 1,
    repair_history: Optional[list[dict[str, Any]]] = None,
    artifacts: Optional[list[dict[str, Any]]] = None,
    receipt_id: Optional[str] = None,
    slug: Optional[str] = None,
) -> Receipt:
    """Assemble a validated Receipt instance according to contracts."""
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    r_id = receipt_id or generate_receipt_id()
    r_slug = slug or generate_receipt_slug()

    receipt_data = {
        "id": r_id,
        "slug": r_slug,
        "repo": repo_name,
        "pr": {
            "number": pr_number,
            "title": pr_title,
            "author": pr_author,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "url": f"https://github.com/{repo_name}/pull/{pr_number}",
        },
        "verdict": verdict,
        "score": score,
        "iterations": iterations,
        "duration_ms": duration_ms,
        "intent": intent,
        "proofs": proofs,
        "suite": suite,
        "mutation": mutation,
        "constraints": constraints,
        "browser": browser,
        "repair_history": repair_history or [],
        "score_breakdown": score_breakdown,
        "limits": limits,
        "artifacts": artifacts or [],
        "created_at": created_at,
    }

    return Receipt(**receipt_data)


def format_receipt_markdown(receipt: Receipt) -> str:
    """Generate an evidence receipt formatted in GitHub Markdown."""
    proof_rows = []
    for p in receipt.proofs:
        valid_mark = "Valid" if not p.vacuous else "Vacuous (No proof)"
        proof_rows.append(
            f"| `{p.criterion_id}` | `{p.test_name}` | `{p.base}` ➔ `{p.head}` | {valid_mark} |"
        )
    proof_table = "\n".join(proof_rows) if proof_rows else "_No testable proofs evaluated._"

    constraint_rows = []
    for c in receipt.constraints:
        res_emoji = "✅" if c.result == "PASS" else "❌"
        constraint_rows.append(f"- {res_emoji} **{c.constraint_id}**: {c.title} (`{c.result}`)")
    constraint_list = "\n".join(constraint_rows) if constraint_rows else "_No active constraints checked._"

    limits_list = "\n".join(f"- {lim}" for lim in receipt.limits) if receipt.limits else "_None._"

    return f"""# 🧾 VERIFICATION RECEIPT: [{receipt.verdict}] (Score: {receipt.score}/100)

**Repository**: `{receipt.repo}` • **PR #{receipt.pr.number}**: "{receipt.pr.title}"  
**Author**: `{receipt.pr.author}` • **Public Record**: `http://localhost:3000/r/{receipt.slug}`  
**Commits**: `{receipt.pr.base_sha[:7]}` ➔ `{receipt.pr.head_sha[:7]}` • **Duration**: {receipt.duration_ms / 1000.0:.1f}s ({receipt.iterations} iter)

---

### 1. Acceptance Criteria & Fail-Before Proofs
| Criterion | Test Name | Base ➔ Head | Evidence Status |
|---|---|:---:|:---:|
{proof_table}

### 2. Regression Suite Check
- **Base Commit**: {receipt.suite.base.passed} passed, {receipt.suite.base.failed} failed
- **Head Commit**: {receipt.suite.head.passed} passed, {receipt.suite.head.failed} failed
- **Regressions**: {len(receipt.suite.regressions)} detected {f"(`{receipt.suite.regressions}`)" if receipt.suite.regressions else "✅ Clean"}

### 3. Mutation Testing Score on Changed Lines
- **Score**: {receipt.mutation.score * 100:.0f}% ({receipt.mutation.killed} killed / {receipt.mutation.survived} survived / {receipt.mutation.mutants} total)

### 4. Scar Tissue Constraints Enforced
{constraint_list}

### 5. Limits & Exclusions
{limits_list}

---
<sub>Verified autonomously by <b>Receipt</b> • Cryptographic Digest Recorded</sub>
"""
