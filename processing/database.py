from __future__ import annotations

from pathlib import Path
import sqlite3

DB_ROOT = Path(r"Q:\data\Databases")


def resolve_config_db(rel_name: str) -> str:
    return str(DB_ROOT / rel_name)


def connect_sqlite(db_path: str, *, row_factory: bool = True) -> sqlite3.Connection:
    path = Path(db_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Database file does not exist: {path}")

    con = sqlite3.connect(str(path))
    if row_factory:
        con.row_factory = sqlite3.Row
    return con