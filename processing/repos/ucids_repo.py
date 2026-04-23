from __future__ import annotations

from typing import Any, Dict, List, Optional

from processing.repos.base_repository import BaseRepository


class UcidsRepository(BaseRepository):
    table_name = "ucids"

    def __init__(self, *, db_filename: str = "ucids.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)

    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT id, poster, client, ucid1, ucid2
                FROM {self.table_name}
                ORDER BY id ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT id, poster, client, ucid1, ucid2
                FROM {self.table_name}
                WHERE poster LIKE ? OR client LIKE ? OR ucid1 LIKE ? OR ucid2 LIKE ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (pat, pat, pat, pat, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_row(
        self,
        *,
        id_: int,
        poster: str,
        client: str,
        ucid1: str = "",
        ucid2: str = "",
    ) -> None:
        with self._connect() as con:
            con.execute(
                f"""
                INSERT INTO {self.table_name} (id, poster, client, ucid1, ucid2)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(id_),
                    str(poster),
                    str(client),
                    str(ucid1) if ucid1 is not None else "",
                    str(ucid2) if ucid2 is not None else "",
                ),
            )
            con.commit()

    def get_by_client_poster(self, *, client: str, poster: str) -> Optional[Dict[str, Any]]:
        client_key = str(client or "").strip()
        poster_key = str(poster or "").strip()
        if not client_key or not poster_key:
            return None

        with self._connect() as con:
            row = con.execute(
                f"""
                SELECT id, poster, client, ucid1, ucid2
                FROM {self.table_name}
                WHERE LOWER(TRIM(client)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(poster)) = LOWER(TRIM(?))
                LIMIT 1
                """,
                (client_key, poster_key),
            ).fetchone()

        return dict(row) if row else None

    def list_poster_options(self) -> list[tuple[str, str]]:
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT DISTINCT poster
                FROM {self.table_name}
                WHERE TRIM(COALESCE(poster, '')) <> ''
                ORDER BY poster COLLATE NOCASE
                """
            ).fetchall()

        return [(str(r["poster"]), str(r["poster"])) for r in rows]

    def list_client_options(self, poster: str | None = None) -> list[tuple[str, str]]:
        poster = str(poster or "").strip()

        with self._connect() as con:
            if poster:
                rows = con.execute(
                    f"""
                    SELECT DISTINCT client
                    FROM {self.table_name}
                    WHERE LOWER(TRIM(poster)) = LOWER(TRIM(?))
                      AND TRIM(COALESCE(client, '')) <> ''
                    ORDER BY client COLLATE NOCASE
                    """,
                    (poster,),
                ).fetchall()
            else:
                rows = con.execute(
                    f"""
                    SELECT DISTINCT client
                    FROM {self.table_name}
                    WHERE TRIM(COALESCE(client, '')) <> ''
                    ORDER BY client COLLATE NOCASE
                    """
                ).fetchall()

        return [(str(r["client"]), str(r["client"])) for r in rows]

    def upsert_client_poster_ucids(
        self,
        *,
        client: str,
        poster: str,
        ucid1: str = "",
        ucid2: str = "",
    ) -> None:
        client = str(client or "").strip()
        poster = str(poster or "").strip()
        ucid1 = str(ucid1 or "").strip()
        ucid2 = str(ucid2 or "").strip()

        if not client or not poster:
            return

        existing = self.get_by_client_poster(client=client, poster=poster)

        with self._connect() as con:
            if existing:
                con.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET ucid1 = ?, ucid2 = ?
                    WHERE id = ?
                    """,
                    (ucid1, ucid2, int(existing["id"])),
                )
            else:
                next_id = self.next_id()
                con.execute(
                    f"""
                    INSERT INTO {self.table_name} (id, poster, client, ucid1, ucid2)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (next_id, poster, client, ucid1, ucid2),
                )
            con.commit()