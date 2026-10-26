import json
from typing import Any, Dict, List, Optional
import structlog

from receipt_api.config import get_settings
from receipt_api.github.client import GitHubClient

logger = structlog.get_logger(__name__)

RECEIPT_COMMENT_MARKER = "<!-- receipt-summary-comment -->"


def format_receipt_markdown(receipt_data: Dict[str, Any], public_url: Optional[str] = None) -> str:
    """Format receipt JSON into a polished, idempotent GitHub markdown comment."""
    settings = get_settings()
    base_url = public_url or settings.public_url or "http://localhost:3000"

    receipt_id = receipt_data.get("id", "rcpt_unknown")
    verdict = receipt_data.get("verdict", "NEEDS_REVIEW")
    score = receipt_data.get("score", 0)
    slug = receipt_data.get("public_slug", receipt_id)
    web_url = f"{base_url}/r/{slug}"

    verdict_emoji = "✅" if verdict == "VERIFIED" else "⚠️" if verdict == "NEEDS_REVIEW" else "❌"
    
    breakdown = receipt_data.get("score_breakdown", {})
    proofs_score = breakdown.get("proofs", 0)
    regression_score = breakdown.get("regression", 0)
    test_strength_score = breakdown.get("test_strength", 0)
    constraints_score = breakdown.get("constraints", 0)
    browser_score = breakdown.get("browser", 0)

    lines = [
        RECEIPT_COMMENT_MARKER,
        f"## 🧾 Receipt Verification Report: `{verdict_emoji} {verdict}`",
        "",
        f"**Overall Score:** `{score}/100` &nbsp;|&nbsp; **Receipt ID:** `{receipt_id}` &nbsp;|&nbsp; [👉 View Full Interactive Receipt]({web_url})",
        "",
        "### Verification Scorecard",
        "| Evaluation Dimension | Weight | Subscore | Status |",
        "| :--- | :---: | :---: | :--- |",
        f"| **Acceptance Criteria Proofs** | 25% | `{proofs_score}/100` | {'🟢 Pass' if proofs_score >= 80 else '🔴 Fail'} |",
        f"| **Regression Test Suite** | 25% | `{regression_score}/100` | {'🟢 Pass' if regression_score >= 80 else '🔴 Fail'} |",
        f"| **Targeted Mutation Strength** | 20% | `{test_strength_score}/100` | {'🟢 High' if test_strength_score >= 70 else '🟡 Low'} |",
        f"| **Scar Tissue Invariants** | 20% | `{constraints_score}/100` | {'🟢 Clear' if constraints_score >= 80 else '🔴 Blocked'} |",
        f"| **Browser QA & Visual Checks** | 10% | `{browser_score}/100` | {'🟢 Verified' if browser_score >= 80 else '⚪ Skipped/Warn'} |",
        "",
    ]

    # Acceptance Criteria Table
    criteria = receipt_data.get("acceptance_criteria", [])
    if criteria:
        lines.append("### Acceptance Criteria Proof Matrix")
        lines.append("| Criterion | Type | Base Status | Head Status | Result |")
        lines.append("| :--- | :---: | :---: | :---: | :---: |")
        for c in criteria:
            desc = c.get("description", "")
            kind = c.get("kind", "feature")
            base = c.get("base_status", "N/A")
            head = c.get("head_status", "N/A")
            passed = c.get("status") == "PASS"
            icon = "✅ PASS" if passed else "❌ FAIL"
            lines.append(f"| {desc} | `{kind}` | `{base}` | `{head}` | {icon} |")
        lines.append("")

    # Scar Tissue Institutional Violations
    constraints = receipt_data.get("constraints", [])
    violations = [c for c in constraints if c.get("status") in ("VIOLATED", "FAIL")]
    if violations:
        lines.append("### ⚠️ Scar Tissue Constraint Violations")
        for v in violations:
            c_id = v.get("id") or v.get("check_id") or "constraint"
            title = v.get("title") or v.get("message") or "Institutional constraint violation"
            evidence = v.get("evidence", [])
            evidence_str = ""
            if evidence:
                evidence_links = [f"[{e.get('type', 'ref')} #{e.get('id', '')}]({e.get('url', '#')})" for e in evidence[:3]]
                evidence_str = " (Learned from: " + ", ".join(evidence_links) + ")"
            lines.append(f"- ❌ **`{c_id}`**: {title}{evidence_str}")
        lines.append("")
    elif constraints:
        lines.append(f"### 🛡️ Scar Tissue: {len(constraints)} institutional constraints satisfied.")
        lines.append("")

    # Mutation Survivors
    mutation = receipt_data.get("mutation", {})
    if mutation and mutation.get("applicable", True):
        killed = mutation.get("killed", 0)
        total = mutation.get("total", 0)
        survivors = mutation.get("survivors", [])
        lines.append(f"### 🧬 Mutation Testing: `{killed}/{total}` mutants killed (`{int((killed/total)*100) if total else 100}%`)")
        if survivors:
            lines.append(f"Found {len(survivors)} surviving mutants on modified lines:")
            for s in survivors[:3]:
                loc = f"`{s.get('file', '')}:{s.get('line', '')}`"
                op = s.get("op", "mutation")
                lines.append(f"- Surviving mutant at {loc} ({op})")
        lines.append("")

    # Repair History Recovery Curve
    repairs = receipt_data.get("repair_history", [])
    if repairs:
        lines.append("### 🔄 Auto-Repair Recovery Curve")
        curve_parts = [f"Iter {r.get('iteration', idx+1)}: `{r.get('score', 0)}/100`" for idx, r in enumerate(repairs)]
        lines.append(" → ".join(curve_parts))
        lines.append("")

    lines.append("---")
    lines.append(f"*Verified with [Receipt](https://github.com/Paramveersingh-S/Receipt) · Zero-trust sandbox verification for agent PRs*")

    return "\n".join(lines)


async def post_commit_status(
    client: GitHubClient,
    repo_full_name: str,
    head_sha: str,
    state: str,  # pending | success | failure | error
    description: str,
    target_url: str,
) -> Dict[str, Any]:
    """Publish commit status to GitHub commit."""
    endpoint = f"/repos/{repo_full_name}/statuses/{head_sha}"
    payload = {
        "state": state,
        "target_url": target_url,
        "description": description[:140],  # GitHub limits to 140 chars
        "context": "receipt/verify",
    }
    try:
        res = await client.http_client.post(endpoint, json=payload)
        res.raise_for_status()
        logger.info("github_status_posted", sha=head_sha, state=state)
        return res.json()
    except Exception as e:
        logger.warning("failed_to_post_github_status", error=str(e), sha=head_sha)
        return {"error": str(e)}


async def post_or_update_pr_comment(
    client: GitHubClient,
    repo_full_name: str,
    pr_number: int,
    markdown_body: str,
) -> Dict[str, Any]:
    """Post receipt markdown summary to PR, updating previous comment if it exists."""
    endpoint = f"/repos/{repo_full_name}/issues/{pr_number}/comments"
    existing_comment_id = None

    try:
        async for comment in client.get_paginated(endpoint):
            body = comment.get("body", "")
            if RECEIPT_COMMENT_MARKER in body:
                existing_comment_id = comment.get("id")
                break
    except Exception as e:
        logger.warning("failed_to_list_pr_comments", error=str(e), pr=pr_number)

    if existing_comment_id:
        # Update existing comment
        patch_endpoint = f"/repos/{repo_full_name}/issues/comments/{existing_comment_id}"
        try:
            res = await client.http_client.patch(patch_endpoint, json={"body": markdown_body})
            res.raise_for_status()
            logger.info("updated_pr_receipt_comment", comment_id=existing_comment_id)
            return res.json()
        except Exception as e:
            logger.warning("failed_to_update_comment", error=str(e), comment_id=existing_comment_id)
            return {"error": str(e)}
    else:
        # Create new comment
        try:
            res = await client.http_client.post(endpoint, json={"body": markdown_body})
            res.raise_for_status()
            logger.info("created_pr_receipt_comment", pr=pr_number)
            return res.json()
        except Exception as e:
            logger.warning("failed_to_create_comment", error=str(e), pr=pr_number)
            return {"error": str(e)}


async def publish_receipt_to_github(
    receipt_data: Dict[str, Any],
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    client: Optional[GitHubClient] = None,
) -> Dict[str, Any]:
    """Coordinate status update and PR comment posting."""
    close_client = False
    if client is None:
        client = GitHubClient()
        close_client = True

    try:
        verdict = receipt_data.get("verdict", "NEEDS_REVIEW")
        score = receipt_data.get("score", 0)
        slug = receipt_data.get("public_slug", receipt_data.get("id", "unknown"))
        settings = get_settings()
        web_url = f"{settings.public_url or 'http://localhost:3000'}/r/{slug}"

        state = "success" if verdict == "VERIFIED" else "failure"
        description = f"Receipt: {verdict} ({score}/100)"

        status_res = await post_commit_status(
            client=client,
            repo_full_name=repo_full_name,
            head_sha=head_sha,
            state=state,
            description=description,
            target_url=web_url,
        )

        markdown_body = format_receipt_markdown(receipt_data, public_url=settings.public_url)
        comment_res = await post_or_update_pr_comment(
            client=client,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            markdown_body=markdown_body,
        )

        return {
            "status": status_res,
            "comment": comment_res,
        }
    finally:
        if close_client:
            await client.close()
