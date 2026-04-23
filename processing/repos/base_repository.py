from __future__ import annotations

import sqlite3
from typing import Optional

from processing.database import resolve_config_db, connect_sqlite


class BaseRepository:
    def __init__(self, *, db_filename: str, db_path: Optional[str] = None):
        self.db_path = db_path or resolve_config_db(db_filename)

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, row_factory=True)

    def next_id(self) -> int:
        with self._connect() as con:
            row = con.execute(
                f"SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM {self.table_name}"
            ).fetchone()
        return int(row["nxt"]) if row and row["nxt"] is not None else 1
