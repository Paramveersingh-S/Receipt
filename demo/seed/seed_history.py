import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
import httpx

SEED_DIR = Path(__file__).resolve().parent
SNAPSHOT_FILE = SEED_DIR / "snapshot.json"
PLANTED_LESSONS_FILE = SEED_DIR / "planted_lessons.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_ground_truth(snapshot: Dict[str, Any], planted: List[Dict[str, Any]]) -> bool:
    """Verify that all planted lessons cite PRs that actually exist in the snapshot."""
    pr_numbers = {pr["number"] for pr in snapshot.get("pull_requests", [])}
    issue_numbers = {issue["number"] for issue in snapshot.get("issues", [])}

    print(f"Validating {len(planted)} planted lessons against snapshot ({len(pr_numbers)} PRs, {len(issue_numbers)} issues)...")
    assert len(planted) >= 7, f"Expected >= 7 planted lessons, found {len(planted)}"

    for lesson in planted:
        lesson_id = lesson["id"]
        for pr_num in lesson["evidence_pr_numbers"]:
            if pr_num not in pr_numbers and pr_num not in issue_numbers:
                raise ValueError(
                    f"Planted lesson '{lesson_id}' references non-existent PR/issue #{pr_num}!"
                )
        print(f"  [OK] Lesson '{lesson_id}': {lesson['title']} (PRs: {lesson['evidence_pr_numbers']})")

    print("All planted lessons validated successfully with 100% evidence resolution.")
    return True


def seed_github_repo(token: str, repo_name: str, snapshot: Dict[str, Any]) -> None:
    """Optionally seed a live GitHub repository via REST API if token provided."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30.0) as client:
        # Check repo access
        resp = client.get(f"/repos/{repo_name}")
        if resp.status_code != 200:
            print(f"Error accessing GitHub repository {repo_name}: {resp.status_code} - {resp.text}")
            return
        print(f"Live GitHub repository {repo_name} accessible. Ready for webhook/status attachment.")


def main():
    parser = argparse.ArgumentParser(description="Seed and validate TipJar Shop history")
    parser.add_argument("--validate-only", action="store_true", help="Validate planted lessons against snapshot")
    parser.add_argument("--live", action="store_true", help="Push to live GitHub repo using GITHUB_TOKEN")
    parser.add_argument("--repo", type=str, default="Paramveersingh-S/receipt-demo-shop", help="Target repo")
    args = parser.parse_args()

    snapshot = load_json(SNAPSHOT_FILE)
    planted = load_json(PLANTED_LESSONS_FILE)

    validate_ground_truth(snapshot, planted)

    if args.live:
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN environment variable is required for live seeding.")
            sys.exit(1)
        seed_github_repo(token, args.repo, snapshot)


if __name__ == "__main__":
    main()
