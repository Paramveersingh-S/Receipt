import hashlib
import hmac
import os
import time
from typing import Any, Dict, Optional

import structlog
from sqlmodel import Session, select

from receipt_api.config import get_settings
from receipt_api.events import emit_event
from receipt_api.models import DBRun, Repo

logger = structlog.get_logger(__name__)


def verify_github_signature(
    payload_body: bytes,
    signature_header: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """Verify that the payload matches the GitHub HMAC-SHA256 signature."""
    settings = get_settings()
    webhook_secret = secret or settings.github_webhook_secret

    if not signature_header:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    received_sig = signature_header[len(prefix):]
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(received_sig, expected_sig)


def handle_webhook_event(
    event_type: str,
    payload: Dict[str, Any],
    session: Session,
) -> Dict[str, Any]:
    """Process an authenticated GitHub webhook payload."""
    logger.info("webhook_received", event_type=event_type, action=payload.get("action"))

    if event_type == "pull_request":
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})

        repo_full_name = repo_data.get("full_name", "")
        pr_number = pr_data.get("number", 0)
        base_sha = pr_data.get("base", {}).get("sha", "")
        head_sha = pr_data.get("head", {}).get("sha", "")
        title = pr_data.get("title", "")
        author = pr_data.get("user", {}).get("login", "")

        # Look up repo in database
        db_repo = session.exec(select(Repo).where(Repo.full_name == repo_full_name)).first()
        repo_id = db_repo.id if db_repo else f"repo_{os.urandom(4).hex()}"

        if action in ("opened", "synchronize", "reopened"):
            run_id = f"run_{int(time.time())}_{os.urandom(3).hex()}"

            db_run = DBRun(
                id=run_id,
                repo_id=repo_id,
                pr_number=pr_number,
                base_sha=base_sha,
                head_sha=head_sha,
                state="pending",
                iteration=1,
            )
            session.add(db_run)
            session.commit()

            emit_event(
                run_id=run_id,
                event_type="run.enqueued",
                payload={
                    "run_id": run_id,
                    "repo": repo_full_name,
                    "pr_number": pr_number,
                    "base_sha": base_sha,
                    "head_sha": head_sha,
                    "title": title,
                    "author": author,
                },
                session=session,
            )

            logger.info("run_enqueued_from_webhook", run_id=run_id, pr_number=pr_number)
            return {
                "status": "enqueued",
                "run_id": run_id,
                "pr_number": pr_number,
                "action": action,
            }

        return {"status": "ignored", "action": action}

    elif event_type == "ping":
        return {"status": "pong", "zen": payload.get("zen")}

    return {"status": "received", "event_type": event_type}
