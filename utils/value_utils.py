from __future__ import annotations

import pandas as pd


def is_blank(value) -> bool:
    """Return True if value is None, NaN, empty, or the string 'nan'."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    return s == "" or s.lower() == "nan"


def coerce_str(value) -> str:
    """Convert a value to a clean string, returning '' for blank/NaN/None."""
    if is_blank(value):
        return ""
    return str(value).strip()


def normalize_code(value) -> str:
    """Normalize a service/product code: strip whitespace and uppercase."""
    return str(value or "").strip().upper()
