import json
from typing import Dict, Optional
from sqlmodel import Session

from receipt_api.models import Artifact
from receipt_api.repair.patcher import FailureBundle


class ExternalAgentRepair:
    """Formats failure bundles for external coding agents (Claude Code, Cursor, Alan) and MCP."""

    @staticmethod
    def format_failure_comment(bundle: FailureBundle, repo_full_name: str, pr_number: int) -> str:
        """Construct detailed markdown comment for GitHub PR feedback loop."""
        lines = [
            f"### ❌ Receipt Verification Failed (Score: {bundle.score}/100 — Verdict: {bundle.verdict})",
            "",
            "Receipt discovered invariant violations and proof gaps on this PR branch.",
            "Please review the failure bundle below and push a fix commit:",
            "",
        ]

        if bundle.constraint_violations:
            lines.append("#### 🛡️ Institutional Constraint Violations (Scar Tissue)")
            for cv in bundle.constraint_violations:
                lines.append(f"- **{cv}**")
            lines.append("")

        if bundle.surviving_mutants:
            lines.append("#### 🧬 Surviving Mutants (Untested Code Hunks)")
            for sm in bundle.surviving_mutants[:5]:
                lines.append(f"- `{sm}`")
            lines.append("")

        if bundle.failing_proofs:
            lines.append("#### ⚠️ Failing Acceptance Criteria Proofs")
            for fp in bundle.failing_proofs:
                lines.append(f"- Proof criterion `{fp}` failed on PR head commit.")
            lines.append("")

        lines.extend([
            "> **Tip:** Run `receipt_briefing` or inspect `contracts/fixtures/` to view exact invariant specifications.",
            f"> Re-verifying automatically when new commits are pushed to `https://github.com/{repo_full_name}/pull/{pr_number}`.",
        ])
        return "\n".join(lines)
