from sqlalchemy import text
from sqlmodel import Session, select
import receipt_api.db as db_module
from receipt_api.db import init_db
from receipt_api.models import Constraint, Repo, RunEvent


def test_database_initialization_and_fts():
    init_db()
    with db_module.engine.connect() as conn:
        # Check FTS table exists
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='constraints_fts'")
        ).fetchone()
        assert result is not None, "constraints_fts virtual table was not created"

    # Test inserting and reading model
    with Session(db_module.engine) as session:
        repo = Repo(
            id="repo_test_1",
            full_name="test-org/test-repo",
            default_branch="main",
            stack="python",
        )
        session.add(repo)
        session.commit()

        queried = session.get(Repo, "repo_test_1")
        assert queried is not None
        assert queried.full_name == "test-org/test-repo"


def test_fts5_indexing_and_search():
    init_db()
    with db_module.engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO constraints_fts (id, title, rule, why) "
                "VALUES ('sc_test_1', 'Integer cents rule', 'Never use float for money amounts', 'Rounding drift causes penny mismatches')"
            )
        )
        conn.commit()

        cursor = conn.execute(
            text("SELECT id FROM constraints_fts WHERE constraints_fts MATCH 'float money'")
        )
        rows = cursor.fetchall()
        assert len(rows) > 0
        assert rows[0][0] == "sc_test_1"
