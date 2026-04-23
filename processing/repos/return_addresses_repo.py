from __future__ import annotations

from typing import Any, Dict, List, Optional

from processing.repos.base_repository import BaseRepository


class ReturnAddressesRepository(BaseRepository):
    table_name = "return_addresses"

    def __init__(self, *, db_filename: str = "return_addresses.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)

    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(f"SELECT ID, contact_name, address1, address2, address3, Town, postcode FROM {self.table_name} ORDER BY ID ASC LIMIT ?",
                (int(limit),),).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(f"""SELECT ID, contact_name, address1, address2, address3, Town, postcode FROM {self.table_name} WHERE
                               contact_name LIKE ? OR address1 LIKE ? OR address2 LIKE ? OR address3 LIKE ? OR Town LIKE ? OR postcode LIKE ?
                               ORDER BY ID ASC
                               LIMIT ?""",(pat, pat, pat, pat, pat, pat, int(limit),),).fetchall()
        return [dict(r) for r in rows]

    def insert_row(self,*,id_: int,contact_name: str,address1: str,address2: str = "",address3: str = "",town: str,postcode: str,) -> None:
        with self._connect() as con:
            con.execute(f"""INSERT INTO {self.table_name} (ID, contact_name, address1, address2, address3, Town, postcode)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (int(id_),str(contact_name),str(address1),str(address2) if address2 is not None else "",
                         str(address3) if address3 is not None else "",str(town),str(postcode)))
            con.commit()
    
    def list_options(repo: ReturnAddressesRepository) -> list[tuple[str, str]]:
        rows = repo.list_all(limit=100000)

        names: list[str] = []
        seen: set[str] = set()

        for row in rows:
            name = str(row.get("contact_name", "") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)

        names.sort(key=lambda x: x.lower())
        return [(name, name) for name in names]