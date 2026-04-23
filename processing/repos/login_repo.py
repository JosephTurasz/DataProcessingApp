from __future__ import annotations

from typing import List, Dict, Any, Optional

from processing.repos.base_repository import BaseRepository

_ALLOWED_TABLE_NAMES = frozenset({"mailmark_logins", "mixed_weight_logins"})

class LoginRepository(BaseRepository):
    def __init__(self, *, db_filename: str = "mailmark_logins.db", table_name: str = "mailmark_logins", db_path: Optional[str] = None):
        if table_name not in _ALLOWED_TABLE_NAMES:
            raise ValueError(f"Invalid table name: {table_name!r}")
        self.table_name = table_name
        super().__init__(db_filename=db_filename, db_path=db_path)

    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(f"SELECT ID, Name, Username, Password FROM {self.table_name} ORDER BY ID ASC LIMIT ?",
                (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pattern = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(f"SELECT ID, Name, Username, Password FROM {self.table_name} WHERE Name LIKE ? OR Username LIKE ? ORDER BY ID ASC LIMIT ?",
                (pattern, pattern, int(limit))).fetchall()
        return [dict(r) for r in rows]

    def insert_row(self, *, id_: int, name: str, username: str, password: str) -> None:
        with self._connect() as con:
            con.execute(
                f"INSERT INTO {self.table_name} (ID, Name, Username, Password) VALUES (?, ?, ?, ?)",
                (int(id_), str(name), str(username), str(password)),)
            con.commit()