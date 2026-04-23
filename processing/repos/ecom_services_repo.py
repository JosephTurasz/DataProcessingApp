from __future__ import annotations

from typing import Any, Dict, List, Optional

from processing.repos.base_repository import BaseRepository


class EcomServicesRepository(BaseRepository):
    table_name = "ecom_services"

    def __init__(self, *, db_filename: str = "ecom_services.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)

    # ---------------- Query / browser methods ----------------
    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(f"""SELECT id, name, new_code, old_code, replacement_code, max_weight_g, min_length_mm, min_width_mm,
                               min_height_mm, max_length_mm, max_width_mm, max_height_mm FROM {self.table_name}
                               ORDER BY id ASC
                               LIMIT ?""",(int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(f"""SELECT id, name, new_code, old_code, replacement_code, max_weight_g, min_length_mm, min_width_mm, min_height_mm,
                               max_length_mm, max_width_mm, max_height_mm FROM {self.table_name}
                               WHERE name LIKE ? OR new_code LIKE ? OR old_code LIKE ? OR replacement_code LIKE ?
                               ORDER BY id ASC
                               LIMIT ?""",(pat, pat, pat, pat, int(limit))).fetchall()
        return [dict(r) for r in rows]

    def insert_row(self,*,id_: int,name: str,new_code: str,old_code: str,replacement_code: str,max_weight_g: int,min_length_mm: int,min_width_mm: int,
                   min_height_mm: int,max_length_mm: int | None,max_width_mm: int | None,max_height_mm: int | None,) -> None:
        with self._connect() as con:
            con.execute(f"""INSERT INTO {self.table_name} (id, name, new_code, old_code, replacement_code, max_weight_g,
                        min_length_mm, min_width_mm, min_height_mm, max_length_mm, max_width_mm, max_height_mm)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (int(id_), str(name), str(new_code), str(old_code), str(replacement_code), int(max_weight_g), int(min_length_mm),
                         int(min_width_mm), int(min_height_mm),
                         None if max_length_mm is None else int(max_length_mm),
                         None if max_width_mm is None else int(max_width_mm),
                         None if max_height_mm is None else int(max_height_mm)))
            con.commit()