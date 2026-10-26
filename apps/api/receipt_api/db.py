import os
from pathlib import Path
from typing import Generator
from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine
from receipt_api.config import get_settings


settings = get_settings()

# Ensure data directory exists
os.makedirs(settings.data_dir, exist_ok=True)

# Connect to SQLite database with WAL mode
connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """Create all SQLModel tables and FTS5 search index."""
    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
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


def get_engine():
    """Return the global SQLAlchemy/SQLModel engine."""
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
