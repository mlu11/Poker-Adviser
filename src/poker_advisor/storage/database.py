"""Database connection management."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from poker_advisor.config import DB_PATH


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_schema()

    def _init_schema(self):
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text()
        with self.connect() as conn:
            conn.executescript(schema_sql)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
