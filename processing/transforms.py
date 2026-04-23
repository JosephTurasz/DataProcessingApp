import re
import pandas as pd
from pandas.api.types import is_object_dtype

class DomainTransforms:
    def append_seeds(self, df: pd.DataFrame, seeds):
        if not seeds:
            return df

        ncols = len(df.columns)
        if ncols < 4:
            raise RuntimeError("Append seeds failed, too few columns")

        def adapt_seed_row(row: list):
            row = list(row or [])
            if ncols == 5:
                base = row[:5]
            elif ncols == 4:
                base = []
                if len(row) > 0: base.append(row[0])
                if len(row) > 1: base.append(row[1])
                if len(row) > 3: base.append(row[3])
                if len(row) > 4: base.append(row[4])
            else:
                base = row[:]
            base = base[:ncols] + [""] * max(0, ncols - len(base))
            return base
        padded_seeds = [adapt_seed_row(s) for s in seeds]
        seed_df = pd.DataFrame(padded_seeds, columns=list(df.columns)[:ncols])
        return pd.concat([df, seed_df], ignore_index=True)

    def append_mmi(self, df: pd.DataFrame, choice, cell_name=None, new_col="MMI", logger=None):
        if choice == "Coopers":
            col_a = df.columns[0]
            col_c = df.columns[2] if len(df.columns) > 2 else df.columns[0]
            df[new_col] = (
                "Y|" + df[col_a].astype(str).str.strip()
                + "|" + df[col_c].astype(str).str.strip())

        elif choice == "Scotts":
            if not cell_name:
                raise ValueError("Cell name is required for Scotts MMI")
            col_a = df.columns[0]
            df[new_col] = df[col_a].astype(str).str.strip() + "|" + cell_name.strip()

        elif choice == "ProHub DMS":
            col_a = df.columns[0]
            col_b = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            col_g = df.columns[6] if len(df.columns) > 6 else df.columns[0]
            stripped_g = df[col_g].astype(str).str.strip()
            invalid_count = int((stripped_g.str.len() <= 12).sum())
            if invalid_count > 0 and logger:
                logger.log(
                    f"[MMI] {invalid_count} row(s) had data too short for ProHub DMS format — MMI may be incomplete for those rows.",
                    "yellow",
                )
            df[new_col] = (
                stripped_g.str[:-12]
                + "00"
                + df[col_a].astype(str).str.strip()
                + df[col_b].astype(str).str.strip().str[1:])
        else:
            raise ValueError(f"Unknown MMI choice: {choice}")
        return df

    @staticmethod
    def update_UCID(df, ucid_map):
        pat = re.compile(r"\b(UCID1|UCID2)\b")
        for col in df.columns:
            if is_object_dtype(df[col]):
                df[col] = df[col].astype(str).str.replace(pat, lambda m: f"UCID {ucid_map[m.group(1)]}", regex=True)
    
    @staticmethod
    def convert_barcode_type(
        df: pd.DataFrame,
        target_length: int,
        barcode_column: str = "BarcodeData") -> pd.DataFrame:
        if barcode_column not in df.columns:
            return df

        def convert(value):
            s = str(value).rstrip(" ")
            return s.ljust(target_length)

        df[barcode_column] = df[barcode_column].map(convert)
        return df

    @staticmethod
    def apply_barcode_padding(
        df: pd.DataFrame,
        padding_char: str,
        barcode_column: str = "BarcodeData") -> pd.DataFrame:
        if barcode_column not in df.columns:
            return df

        def pad(value):
            s = str(value)
            if not s:
                return s
            return s[:-1] + padding_char
        df[barcode_column] = df[barcode_column].map(pad)
        return df