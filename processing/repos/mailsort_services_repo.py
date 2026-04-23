from __future__ import annotations

from typing import Any, Dict, List, Optional

from processing.repos.base_repository import BaseRepository


class MailsortServicesRepository(BaseRepository):
    table_name = "mailsort_services"

    def __init__(self, *, db_filename: str = "mailsort_services.db", db_path: Optional[str] = None):
        super().__init__(db_filename=db_filename, db_path=db_path)

    # ---------------- Query / browser methods ----------------
    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                f"""SELECT Id, service_name, format_code, sortation_code, machinability_code,
                    format, sortation, machinability, mail_category
                    FROM {self.table_name}
                    ORDER BY Id ASC
                    LIMIT ?""",
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
                f"""SELECT Id, service_name, format_code, sortation_code, machinability_code,
                    format, sortation, machinability, mail_category
                    FROM {self.table_name}
                    WHERE service_name LIKE ? OR format_code LIKE ? OR sortation_code LIKE ?
                       OR machinability_code LIKE ? OR mail_category LIKE ?
                    ORDER BY Id ASC
                    LIMIT ?""",
                (pat, pat, pat, pat, pat, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_codes(
        self, *, format_code: str, sortation_code: str, machinability_code: str
    ) -> Dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                f"""SELECT format, sortation, machinability, mail_category
                    FROM {self.table_name}
                    WHERE UPPER(TRIM(format_code))       = UPPER(TRIM(?))
                      AND UPPER(TRIM(sortation_code))    = UPPER(TRIM(?))
                      AND UPPER(TRIM(machinability_code))= UPPER(TRIM(?))
                    LIMIT 1""",
                (format_code, sortation_code, machinability_code),
            ).fetchone()
        return dict(row) if row else None

    def insert_row(
        self,
        *,
        id_: int,
        service_name: str,
        format_code: str,
        sortation_code: str,
        machinability_code: str,
        format: str,
        sortation: str,
        machinability: str,
        mail_category: str,
    ) -> None:
        with self._connect() as con:
            con.execute(
                f"""INSERT INTO {self.table_name}
                    (Id, service_name, format_code, sortation_code, machinability_code,
                     format, sortation, machinability, mail_category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(id_), str(service_name), str(format_code), str(sortation_code),
                 str(machinability_code), str(format), str(sortation),
                 str(machinability), str(mail_category)),
            )
            con.commit()
