from __future__ import annotations

from typing import Iterable, Set, Optional

from processing.repos.base_repository import BaseRepository

_ALLOWED_COLUMN_NAMES = frozenset({"postcode"})

class PostcodesRepository(BaseRepository):
    table_name = "postcodes"

    def __init__(self, *, db_filename: str = "postcodes.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)
        self.column_name = self._detect_postcode_column()

    def _detect_postcode_column(self) -> str:
        with self._connect() as con:
            cols = [r["name"] for r in con.execute(f"PRAGMA table_info({self.table_name})").fetchall()]
        for col in cols:
            if col in _ALLOWED_COLUMN_NAMES:
                return col
        raise RuntimeError(f"postcodes.db: expected column 'postcode' in table '{self.table_name}'")

    def existing_postcode_set(self, values: Iterable[str], *, chunk_size: int = 900) -> Set[str]:
        vals = [str(v) for v in values if str(v).strip()]
        if not vals:
            return set()

        found: Set[str] = set()
        col = self.column_name

        with self._connect() as con:
            cur = con.cursor()
            for i in range(0, len(vals), int(chunk_size)):
                chunk = vals[i : i + int(chunk_size)]
                placeholders = ",".join(["?"] * len(chunk))
                sql = f"SELECT {col} AS pc FROM {self.table_name} WHERE {col} IN ({placeholders})"
                cur.execute(sql, chunk)
                found.update(str(r["pc"]) for r in cur.fetchall())

        return found
    
    def insert_postcode(self, postcode):
        postcode = postcode.strip().upper()

        with self._connect() as con:
            con.execute("INSERT OR IGNORE INTO postcodes(postcode) VALUES (?)",(postcode,),)
            con.commit()