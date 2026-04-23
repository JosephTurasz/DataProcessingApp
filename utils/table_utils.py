import re
import pandas as pd
from collections import defaultdict

_SUFFIX_RE = re.compile(r"^(.*?)(?: \((\d+)\))?$")


def make_unique_columns(columns):
    counts = defaultdict(int)
    new_cols = []

    for col in columns:
        col = str(col).strip()

        m = _SUFFIX_RE.match(col)
        base = (m.group(1) or "").strip()
        num = m.group(2)

        if not base:
            base = "Column"

        if num is not None:
            n = int(num)
            counts[base] = max(counts[base], n + 1)
            new_cols.append(f"{base} ({n})")
            continue

        if counts[base] == 0:
            new_cols.append(base)
        else:
            new_cols.append(f"{base} ({counts[base]})")

        counts[base] += 1

    return new_cols

def pad_rows(rows):
    if not rows:
        return rows, 0

    max_cols = max(len(r) for r in rows)
    padded = [
        r + [""] * (max_cols - len(r))
        for r in rows
    ]
    return padded, max_cols

def trailing_empty_run(row):
    cnt = 0
    for c in reversed(row):
        if str(c).strip() == "":
            cnt += 1
        else:
            break
    return cnt

def is_duplicate_header(r1, r2):
    return [c.strip().lower() for c in r1] == [c.strip().lower() for c in r2]