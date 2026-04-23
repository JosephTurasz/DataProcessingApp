from __future__ import annotations

from pathlib import Path
import sqlite3
import sys


def resolve_config_db(rel_name: str) -> str:
    rel_path = Path("config") / "databases" / rel_name

    search_roots: list[Path] = []

    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        search_roots.append(Path(bundle))
    search_roots.append(Path(__file__).resolve().parent.parent)
    search_roots.append(Path.cwd())

    for root in search_roots:
        candidate = root / rel_path
        if candidate.exists():
            return str(candidate)
    return str(search_roots[1] / rel_path)


def connect_sqlite(db_path: str, *, row_factory: bool = True) -> sqlite3.Connection:
    path = Path(db_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Database file does not exist: {path}")

    con = sqlite3.connect(str(path))
    if row_factory:
        con.row_factory = sqlite3.Row
    return con