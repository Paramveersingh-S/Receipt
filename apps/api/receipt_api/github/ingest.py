import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from sqlmodel import Session, select

from receipt_api.events import emit_event
from receipt_api.github.client import GitHubClient
from receipt_api.models import GHEvent, Repo

logger = structlog.get_logger(__name__)


def parse_iso_datetime(val: Optional[str]) -> datetime.datetime:
    if not val:
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        dt = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def ingest_from_snapshot(
    repo_id: str,
    snapshot_path: Path,
    session: Session,
) -> Dict[str, int]:
    """Idempotently ingest repository history from a JSON snapshot into gh_events."""
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")

    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    repo_info = data.get("repository", {})
    repo_full_name = repo_info.get("full_name", "Paramveersingh-S/receipt-demo-shop")

    stats = {
        "prs": 0,
        "reviews": 0,
        "comments": 0,
        "reverts": 0,
        "issues": 0,
        "total_new": 0,
        "duplicates_skipped": 0,
    }

    prs = data.get("pull_requests", [])
    total_items = len(prs)

    for idx, pr in enumerate(prs, start=1):
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_author = pr["author"]
        pr_created_at = parse_iso_datetime(pr.get("merged_at") or pr.get("created_at"))
        pr_id_str = f"pr_{pr_number}"
        pr_url = f"https://github.com/{repo_full_name}/pull/{pr_number}"

        # 1. Ingest PR Event
        existing_pr = session.exec(
            select(GHEvent).where(GHEvent.repo_id == repo_id, GHEvent.gh_id == pr_id_str)
        ).first()

        if not existing_pr:
            is_revert = "revert" in pr_title.lower()
            event_kind = "revert" if is_revert else "pr"
            if is_revert:
                stats["reverts"] += 1
            else:
                stats["prs"] += 1

            session.add(
                GHEvent(
                    id=f"evt_{pr_id_str}",
                    repo_id=repo_id,
                    kind=event_kind,
                    gh_id=pr_id_str,
                    url=pr_url,
                    author=pr_author,
                    created_at=pr_created_at,
                    payload_json=json.dumps(pr),
                )
            )
            stats["total_new"] += 1
        else:
            stats["duplicates_skipped"] += 1

        # 2. Ingest Reviews & Comments
        for r_idx, rev in enumerate(pr.get("reviews", []), start=1):
            rev_id_str = f"review_{pr_number}_{r_idx}"
            existing_rev = session.exec(
                select(GHEvent).where(GHEvent.repo_id == repo_id, GHEvent.gh_id == rev_id_str)
            ).first()

            if not existing_rev:
                stats["reviews"] += 1
                session.add(
                    GHEvent(
                        id=f"evt_{rev_id_str}",
                        repo_id=repo_id,
                        kind="review",
                        gh_id=rev_id_str,
                        url=f"{pr_url}#pullrequestreview-{r_idx}",
                        author=rev.get("author", "unknown"),
                        created_at=pr_created_at,
                        payload_json=json.dumps(rev),
                    )
                )
                stats["total_new"] += 1
            else:
                stats["duplicates_skipped"] += 1

            for c in rev.get("comments", []):
                c_id_str = f"comment_{c['id']}"
                existing_c = session.exec(
                    select(GHEvent).where(GHEvent.repo_id == repo_id, GHEvent.gh_id == c_id_str)
                ).first()

                if not existing_c:
                    stats["comments"] += 1
                    session.add(
                        GHEvent(
                            id=f"evt_{c_id_str}",
                            repo_id=repo_id,
                            kind="review_comment",
                            gh_id=c_id_str,
                            url=f"{pr_url}#discussion_r{c['id']}",
                            author=rev.get("author", "unknown"),
                            created_at=parse_iso_datetime(c.get("created_at")),
                            payload_json=json.dumps(c),
                        )
                    )
                    stats["total_new"] += 1
                else:
                    stats["duplicates_skipped"] += 1

        emit_event(
            run_id=repo_id,
            event_type="ingest.progress",
            payload={"phase": "pull_requests", "done": idx, "total": total_items},
            session=session,
        )

    # 3. Ingest Issues / Incidents
    issues = data.get("issues", [])
    for issue in issues:
        issue_number = issue["number"]
        issue_id_str = f"issue_{issue_number}"
        existing_issue = session.exec(
            select(GHEvent).where(GHEvent.repo_id == repo_id, GHEvent.gh_id == issue_id_str)
        ).first()

        if not existing_issue:
            is_incident = "incident" in issue.get("title", "").lower()
            stats["issues"] += 1
            session.add(
                GHEvent(
                    id=f"evt_{issue_id_str}",
                    repo_id=repo_id,
                    kind="incident" if is_incident else "issue",
                    gh_id=issue_id_str,
                    url=f"https://github.com/{repo_full_name}/issues/{issue_number}",
                    author=issue.get("author", "incident-bot"),
                    created_at=parse_iso_datetime(issue.get("created_at")),
                    payload_json=json.dumps(issue),
                )
            )
            stats["total_new"] += 1
        else:
            stats["duplicates_skipped"] += 1

    # Update Repo record
    db_repo = session.exec(select(Repo).where(Repo.id == repo_id)).first()
    if db_repo:
        db_repo.last_ingested_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(db_repo)

    session.commit()
    logger.info("ingest_completed", repo_id=repo_id, stats=stats)
    return stats


async def ingest_repository_events(
    repo_id: str,
    full_name: str,
    session: Session,
    snapshot_path: Optional[Path] = None,
) -> Dict[str, int]:
    """Ingest history using snapshot if provided/available, or live GitHub API."""
    default_snapshot = Path(__file__).resolve().parent.parent.parent.parent / "demo" / "seed" / "snapshot.json"
    resolved_snapshot = snapshot_path or (default_snapshot if default_snapshot.exists() else None)

    if resolved_snapshot and resolved_snapshot.exists():
        logger.info("ingesting_from_snapshot", path=str(resolved_snapshot))
        return ingest_from_snapshot(repo_id, resolved_snapshot, session)

    # Live API Ingestion fallback
    client = GitHubClient()
    try:
        stats = {"prs": 0, "reviews": 0, "comments": 0, "reverts": 0, "issues": 0, "total_new": 0, "duplicates_skipped": 0}
        async for pr in client.get_paginated(f"/repos/{full_name}/pulls?state=all"):
            pr_num = pr["number"]
            gh_id = f"pr_{pr_num}"
            existing = session.exec(select(GHEvent).where(GHEvent.gh_id == gh_id)).first()
            if not existing:
                session.add(
                    GHEvent(
                        id=f"evt_{gh_id}",
                        repo_id=repo_id,
                        kind="pr",
                        gh_id=gh_id,
                        url=pr.get("html_url", ""),
                        author=pr.get("user", {}).get("login", "unknown"),
                        created_at=parse_iso_datetime(pr.get("created_at")),
                        payload_json=json.dumps(pr),
                    )
                )
                stats["prs"] += 1
                stats["total_new"] += 1
        session.commit()
        return stats
    finally:
        await client.close()
