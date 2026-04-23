import re
import pandas as pd
from collections import Counter

class DataCleaner:
    CONTROL_CHARS = ''.join(map(chr, range(0, 32)))
    CONTROL_REGEX = re.compile(f"[{re.escape(CONTROL_CHARS)}]")

    def __init__(self, logger):
        self.logger = logger
        self.cleansing_stats = Counter()

    def normalise_row(self, row):
        return ["" if c is None else str(c).strip() for c in row]

    def cleanse_cell_string(self, value):
        if not isinstance(value, str):
            return value

        removed = 0
        s = value

        matches = re.findall(r"_x0{3}[0-9A-Fa-f]{1}_", s)
        if matches:
            removed += sum(len(m) for m in matches)
            s = re.sub(r"_x0{3}[0-9A-Fa-f]{1}_", " ", s)

        control_matches = self.CONTROL_REGEX.findall(s)
        removed += len(control_matches)
        s = self.CONTROL_REGEX.sub(" ", s)

        nbsp = s.count("\xa0")
        if nbsp:
            removed += nbsp
            s = s.replace("\xa0", " ")

        if removed:
            self.cleansing_stats["removed_chars"] += removed
            self.cleansing_stats["modified_cells"] += 1

        return s

    def cleanse_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        self.cleansing_stats.clear()

        df = df.astype(object).where(pd.notnull(df), "")
        df = df.map(self.cleanse_cell_string)
        df = df.replace("", pd.NA)

        before_rows, before_cols = df.shape
        df = df.dropna(how="all")

        cols_to_drop = []
        for col in df.columns:
            header = str(col).strip()
            is_placeholder = (not header) or (re.fullmatch(r"Column\d+", header) is not None)

            col_all_na = df[col].isna().all()
            if hasattr(col_all_na, "all"):
                col_all_na = col_all_na.all()

            if col_all_na and is_placeholder:
                cols_to_drop.append(col)

        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        after_rows, after_cols = df.shape
        df = df.fillna("")

        if self.cleansing_stats["removed_chars"]:
            self.logger.log(
                f"Removed {self.cleansing_stats['removed_chars']} hidden characters "
                f"from {self.cleansing_stats['modified_cells']} cells.",
                "yellow",
            )
        if before_rows > after_rows:
            self.logger.log(f"Dropped {before_rows - after_rows} empty rows", "yellow")

        if before_cols > after_cols:
            self.logger.log(f"Dropped {before_cols - after_cols} empty columns.", "yellow")
        return df

        
    def clean_header_names(self, df: pd.DataFrame, has_header: bool, mode: str = "none") -> pd.DataFrame:
        if not has_header:
            return df
        
        mode = (mode or "none").lower().strip()
        original = list(df.columns)

        if mode == "underscore":
            cleaned = [
                c.replace("_", " ").strip() if isinstance(c, str) else c
                for c in original]
        elif mode == "dot":
            cleaned = [
                c.replace(".", " ").strip() if isinstance(c, str) else c
                for c in original]
        else:
            cleaned = original[:]

        if original != cleaned:
            msg = {"underscore": "Replaced underscores with spaces",
                    "dot": "Replaced dots with spaces",}.get(mode, "Cleaned column names")
            self.logger.log(f"[HEADER] {msg}.", "yellow")
            df.columns = cleaned
        return df