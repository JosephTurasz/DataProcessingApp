from __future__ import annotations

import sqlite3
from typing import List, Optional

from processing.database import connect_sqlite
from processing.repos.base_repository import BaseRepository


class SeedsRepository(BaseRepository):
    def __init__(self, *, db_filename: str = "seeds.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)

    def _connect(self) -> sqlite3.Connection:
        # Seeds queries use positional row access, so row_factory must stay False
        return connect_sqlite(self.db_path, row_factory=False)

    def list_seed_options(self, key: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT Category
                FROM Seeds
                WHERE KEY = ?
                GROUP BY Category
                ORDER BY Category
                """,
                (key,),
            ).fetchall()

        out = []
        for (category,) in rows:
            seed_id = f"{key}::{category}"
            out.append({"label": str(category), "value": seed_id})
        return out

    def get_seed_rows(self, seed_id: str) -> List[List[str]]:
        key, category = seed_id.split("::", 1)

        with self._connect() as con:
            rows = con.execute(
                """
                SELECT Name, Address_1, Address_2, Town, Postcode, DPS
                FROM Seeds
                WHERE KEY = ? AND Category = ?
                ORDER BY ID
                """,
                (key, category),
            ).fetchall()

        return [[("" if v is None else str(v)) for v in r] for r in rows]

    def list_all_rows(self, limit: int = 10000) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT ID, KEY, Category, Name, Address_1, Address_2, Town, Postcode, DPS
                FROM Seeds
                ORDER BY ID ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        out = []
        for r in rows:
            out.append(
                {
                    "ID": r[0],
                    "KEY": r[1],
                    "Category": r[2],
                    "Name": r[3],
                    "Address_1": r[4],
                    "Address_2": r[5],
                    "Town": r[6],
                    "Postcode": r[7],
                    "DPS": r[8],
                }
            )
        return out

    def search_rows(self, query: str, limit: int = 10000) -> list[dict]:
        q = (query or "").strip()
        if not q:
            return self.list_all_rows(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT ID, KEY, Category, Name, Address_1, Address_2, Town, Postcode, DPS
                FROM Seeds
                WHERE KEY LIKE ? OR Category LIKE ? OR Name LIKE ?
                ORDER BY ID ASC
                LIMIT ?
                """,
                (pat, pat, pat, int(limit)),
            ).fetchall()

        out = []
        for r in rows:
            out.append(
                {
                    "ID": r[0],
                    "KEY": r[1],
                    "Category": r[2],
                    "Name": r[3],
                    "Address_1": r[4],
                    "Address_2": r[5],
                    "Town": r[6],
                    "Postcode": r[7],
                    "DPS": r[8],
                }
            )
        return out

    def next_id(self) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT COALESCE(MAX(ID), 0) + 1 AS nxt FROM Seeds"
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else 1

    def insert_row(
        self,
        *,
        id_: int,
        key: str,
        category: str,
        name: str,
        address_1: str,
        address_2: str,
        town: str,
        postcode: str,
        dps: str,
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO Seeds (
                    ID, KEY, Category, Name, Address_1, Address_2, Town, Postcode, DPS
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(id_), key, category, name, address_1, address_2, town, postcode, dps),
            )
            con.commit()