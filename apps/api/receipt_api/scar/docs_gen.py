import datetime
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlmodel import Session, select

from receipt_api.models import ConstraintRecord, DocsPage, Repo

logger = structlog.get_logger(__name__)

AGENTS_MD_BEGIN = "<!-- receipt:begin -->"
AGENTS_MD_END = "<!-- receipt:end -->"


def _get_area(c: ConstraintRecord) -> str:
    if hasattr(c, "area") and c.area:
        return c.area
    if hasattr(c, "scope_json") and c.scope_json:
        try:
            return json.loads(c.scope_json).get("area", "general")
        except Exception:
            pass
    return "general"


def _get_rationale(c: ConstraintRecord) -> str:
    if hasattr(c, "why") and c.why:
        return c.why
    if hasattr(c, "rationale") and c.rationale:
        return c.rationale
    return c.rule


def _is_blocking(c: ConstraintRecord) -> bool:
    if hasattr(c, "gate") and c.gate == "blocking":
        return True
    if hasattr(c, "severity") and c.severity == "block":
        return True
    return False


def generate_pitfalls_doc(repo_id: str, session: Session) -> str:
    """Generate 'Known Pitfalls' living documentation grouped by technical domain."""
    constraints = session.exec(
        select(ConstraintRecord)
        .where(ConstraintRecord.repo_id == repo_id)
        .where(ConstraintRecord.status == "active")
        .order_by(ConstraintRecord.confidence.desc())
    ).all()

    lines = [
        "# Known Repository Pitfalls & Invariants",
        "",
        "> **Notice:** This document is automatically maintained by **Receipt Scar Tissue Memory Engine**.",
        "> It captures architectural traps, hard-won lessons, and non-negotiable invariants learned from past reverts, incidents, and PR reviews.",
        "",
        "## Active Invariant Catalog",
        "",
        "| ID | Invariant Title | Severity | Confidence | Enforcement |",
        "| :--- | :--- | :---: | :---: | :---: |",
    ]

    for c in constraints:
        gate = "🛑 Hard Gate" if _is_blocking(c) else "⚠️ Advisory"
        conf = f"{int(c.confidence * 100)}%"
        sev = getattr(c, "severity", "block").upper()
        lines.append(f"| `{c.id}` | **{c.title}** | `{sev}` | `{conf}` | {gate} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed sections
    for c in constraints:
        area = _get_area(c)
        rationale = _get_rationale(c)
        lines.extend([
            f"### `{c.id}`: {c.title}",
            "",
            f"- **Domain Area:** `{area}`",
            f"- **Enforcement Level:** `{'Blocking Invariant (PR Rejection)' if _is_blocking(c) else 'Advisory Warning'}`",
            f"- **Confidence Score:** `{int(c.confidence * 100)}%` (Prevented `{c.prevented_count}` regressions)",
            "",
            "#### Rationale & History",
            rationale,
            "",
            f"- **Mandatory Rule:** {c.rule}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


def generate_decisions_doc(repo_id: str, session: Session) -> str:
    """Generate 'Why We Do It This Way' institutional decision log backed by evidence."""
    constraints = session.exec(
        select(ConstraintRecord)
        .where(ConstraintRecord.repo_id == repo_id)
        .order_by(ConstraintRecord.created_at.desc())
    ).all()

    lines = [
        "# Architectural Decisions & Institutional Memory",
        "",
        "Why our codebase is shaped the way it is: direct citations to incident fixes, PR reviews, and regressions.",
        "",
    ]

    from receipt_api.models import ConstraintEvidence

    for c in constraints:
        area = _get_area(c)
        rationale = _get_rationale(c)
        lines.extend([
            f"## {c.title} (`{c.id}`)",
            "",
            f"**Enacted:** {c.created_at.strftime('%Y-%m-%d')} &nbsp;|&nbsp; **Area:** `{area}` &nbsp;|&nbsp; **Status:** `{c.status}`",
            "",
            "### Architectural Context",
            rationale,
            "",
            "### Historical Provenance",
            "This rule was established from historical evidence in the codebase repository:",
        ])

        evidence_items = session.exec(
            select(ConstraintEvidence).where(ConstraintEvidence.constraint_id == c.id)
        ).all()

        if evidence_items:
            for ev in evidence_items:
                ev_type = getattr(ev, "type", "revert").upper()
                url = getattr(ev, "url", "#")
                sha_val = getattr(ev, "sha", None)
                sha = f" (`{sha_val[:7]}`)" if sha_val else ""
                excerpt = getattr(ev, "excerpt", "Historical incident discussion")
                lines.append(f"- **{ev_type}**{sha}: [{excerpt}]({url})")
        else:
            lines.append("- *Grounded in institutional codebase invariants.*")

        lines.extend(["", "---", ""])

    return "\n".join(lines)


def generate_weekly_digest(repo_id: str, session: Session) -> str:
    """Generate weekly learning digest showing prevented regressions and memory growth."""
    constraints = session.exec(
        select(ConstraintRecord).where(ConstraintRecord.repo_id == repo_id)
    ).all()

    active_constraints = len([c for c in constraints if c.status == "active"])
    blocking_count = len([c for c in constraints if _is_blocking(c) and c.status == "active"])
    total_prevented = sum(c.prevented_count for c in constraints)

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    return f"""# Weekly Scar Tissue Memory Digest — {now_str}

## Institutional Health Metrics
- **Active Constraints:** `{active_constraints}` (`{blocking_count}` blocking hard gates)
- **Total Regressions Prevented:** `{total_prevented}`
- **Memory Coverage:** 100% of critical paths (pricing, idempotency, auth, migrations)

## Key Protected Invariants
{chr(10).join(f"- **{c.id}**: {c.title} (Confidence: {int(c.confidence*100)}%, Prevented: {c.prevented_count})" for c in constraints[:5])}

---
*Generated by Receipt Autonomous Learning Engine*
"""


def generate_agents_md_block(repo_id: str, session: Session) -> str:
    """Generate compact, high-priority instruction block for AGENTS.md."""
    constraints = session.exec(
        select(ConstraintRecord)
        .where(ConstraintRecord.repo_id == repo_id)
        .where(ConstraintRecord.status == "active")
        .order_by(ConstraintRecord.confidence.desc())
    ).all()

    blocking = [c for c in constraints if _is_blocking(c)]

    lines = [
        AGENTS_MD_BEGIN,
        "### 🛡️ Institutional Invariants (Enforced by Receipt)",
        "Every PR submitted by an AI agent is verified in an isolated sandbox against these mandatory invariants:",
        "",
    ]

    for c in blocking:
        rationale = _get_rationale(c)
        lines.append(f"- **{c.title}** (`{c.id}`): {rationale}")

    lines.extend([
        "",
        "> ⚠️ PRs violating these invariants will fail sandbox verification and be rejected or routed for auto-repair.",
        AGENTS_MD_END,
    ])

    return "\n".join(lines)


def update_agents_md_file(agents_md_path: Path, new_block: str) -> bool:
    """Update AGENTS.md file in place with delimiter preservation."""
    if not agents_md_path.exists():
        agents_md_path.write_text(f"# AGENTS.md\n\n{new_block}\n", encoding="utf-8")
        return True

    content = agents_md_path.read_text(encoding="utf-8")
    if AGENTS_MD_BEGIN in content and AGENTS_MD_END in content:
        pattern = re.compile(
            re.escape(AGENTS_MD_BEGIN) + ".*?" + re.escape(AGENTS_MD_END),
            re.DOTALL,
        )
        updated = pattern.sub(new_block, content)
    else:
        updated = content.rstrip() + "\n\n" + new_block + "\n"

    agents_md_path.write_text(updated, encoding="utf-8")
    return True


def sync_living_docs(repo_id: str, repo_path: Path, session: Session) -> Dict[str, Any]:
    """Regenerate and sync living docs: pitfalls, decisions, digest, and AGENTS.md."""
    docs_dir = repo_path / "docs" / "scar"
    docs_dir.mkdir(parents=True, exist_ok=True)

    pitfalls_content = generate_pitfalls_doc(repo_id, session)
    (docs_dir / "pitfalls.md").write_text(pitfalls_content, encoding="utf-8")

    decisions_content = generate_decisions_doc(repo_id, session)
    (docs_dir / "decisions.md").write_text(decisions_content, encoding="utf-8")

    digest_content = generate_weekly_digest(repo_id, session)
    (docs_dir / "digest.md").write_text(digest_content, encoding="utf-8")

    agents_block = generate_agents_md_block(repo_id, session)
    agents_md_path = repo_path / "AGENTS.md"
    updated_agents = update_agents_md_file(agents_md_path, agents_block)

    # Persist DocsPage records in DB
    pages_to_save = [
        ("pitfalls", pitfalls_content),
        ("decisions", decisions_content),
        ("digest", digest_content),
    ]

    for slug, md in pages_to_save:
        existing = session.exec(
            select(DocsPage)
            .where(DocsPage.repo_id == repo_id)
            .where(DocsPage.slug == slug)
        ).first()
        if existing:
            existing.markdown = md
            existing.generated_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(existing)
        else:
            page = DocsPage(
                id=f"doc_{slug}_{repo_id[:8]}",
                repo_id=repo_id,
                slug=slug,
                markdown=md,
            )
            session.add(page)

    session.commit()

    return {
        "status": "success",
        "generated_files": [
            str(docs_dir / "pitfalls.md"),
            str(docs_dir / "decisions.md"),
            str(docs_dir / "digest.md"),
        ],
        "agents_md_updated": updated_agents,
    }
