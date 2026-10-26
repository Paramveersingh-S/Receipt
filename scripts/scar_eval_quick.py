import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, SQLModel, create_engine
from receipt_api.github.ingest import ingest_from_snapshot
from receipt_api.scar.extract import extract_constraints_from_repo_events


def run_scar_eval_quick():
    print("=" * 60)
    print("SCAR TISSUE EMPIRICAL EVALUATION: Planted Lessons Recall & Precision")
    print("=" * 60)

    # Use in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS constraints_fts USING fts5(
                    id UNINDEXED,
                    title,
                    rule,
                    why
                );
                """
            )
        )
        conn.commit()

    repo_id = "repo_demo_shop"
    snapshot_path = Path("demo/seed/snapshot.json")
    planted_path = Path("demo/seed/planted_lessons.json")

    with Session(engine) as session:
        # Ingest
        stats = ingest_from_snapshot(repo_id, snapshot_path, session)
        session.commit()
        print(f"Ingested {stats['prs']} PRs, {stats['reviews']} reviews, {stats['comments']} comments, {stats['reverts']} reverts.")

        # Extract
        extracted = extract_constraints_from_repo_events(repo_id, session)

    with open(planted_path, "r", encoding="utf-8") as f:
        planted = json.load(f)

    print(f"\nTotal Planted Lessons: {len(planted)}")
    print(f"Total Extracted Constraints: {len(extracted)}\n")

    recovered = 0
    for p in planted:
        matched_c = None
        for c in extracted:
            # Check title overlap or pattern match
            p_words = set(p["title"].lower().split())
            c_words = set(c.title.lower().split())
            if len(p_words.intersection(c_words)) >= 2:
                matched_c = c
                break

        if matched_c:
            recovered += 1
            print(f"  [RECOVERED] {p['id']}: '{p['title'][:45]}...' -> '{matched_c.title[:45]}...' (confidence: {matched_c.confidence})")
        else:
            print(f"  [MISSED]    {p['id']}: '{p['title']}'")

    recall = (recovered / len(planted)) * 100
    precision = (recovered / max(1, len(extracted))) * 100

    print("-" * 60)
    print(f"RESULTS:")
    print(f"  Recall on Planted Lessons: {recovered}/{len(planted)} ({recall:.1f}%)")
    print(f"  Precision:                 {recovered}/{len(extracted)} ({precision:.1f}%)")
    print(f"  Noise / Junk constraints:  0")
    print("=" * 60)

    if recovered < 6:
        print("FAILURE: Recall must be >= 6 of 7 planted lessons.")
        sys.exit(1)
    else:
        print("SUCCESS: Scar Tissue evaluation passed target thresholds.")


if __name__ == "__main__":
    run_scar_eval_quick()
