import os
import uuid
import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
import receipt_api.db as db_module
from receipt_api.db import init_db


@pytest.fixture(autouse=True)
def test_db_isolation(tmp_path):
    """Use a clean temporary SQLite database for each test to ensure test isolation."""
    test_db_path = tmp_path / "test_receipt.db"
    test_engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    old_engine = db_module.engine
    db_module.engine = test_engine

    # Initialize tables and FTS on test engine
    init_db()

    yield test_engine

    db_module.engine = old_engine
