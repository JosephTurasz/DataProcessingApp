from __future__ import annotations

import re
from typing import Any

import pandas as pd

_CURRENCY_RE = re.compile(r"[£$€¥₹,]")

from config.constants import SENTINEL_SELECT
from processing.repos.return_addresses_repo import ReturnAddressesRepository
from utils.value_utils import coerce_str, is_blank


class EcommerceTransforms:
    def __init__(self):
        self._return_address_cache: dict[str, dict[str, Any] | None] = {}

    def collapse_postcode_series(self, series: pd.Series) -> pd.Series:
        s = series.astype(str)
        s = s.str.replace(" ", "", regex=False)
        s = s.str.replace("\t", "", regex=False)
        s = s.str.replace("\n", "", regex=False)
        s = s.str.replace("\r", "", regex=False)
        s = s.str.strip().str.upper()
        return s

    def collapse_text_series(self, series: pd.Series) -> pd.Series:
        s = series.astype(str)
        s = s.str.replace("\t", " ", regex=False)
        s = s.str.replace("\n", " ", regex=False)
        s = s.str.replace("\r", " ", regex=False)
        s = s.str.strip()
        return s

    def normalise_weight_series(self, series: pd.Series) -> pd.Series:
        def convert(value):
            if pd.isna(value):
                return ""

            s = str(value).strip()
            if not s or s.lower() == "nan":
                return ""

            s_lower = s.lower()

            if s_lower.endswith("kg"):
                num = s[:-2].strip()
                try:
                    grams = float(num) * 1000
                except ValueError:
                    return s
                return str(int(grams)) if grams.is_integer() else str(grams)

            if s_lower.endswith("g"):
                num = s[:-1].strip()
                try:
                    grams = float(num)
                except ValueError:
                    return s
                return str(int(grams)) if grams.is_integer() else str(grams)

            try:
                n = float(s)
                return str(int(n)) if n.is_integer() else str(n)
            except ValueError:
                return s

        return series.map(convert)

    def apply_info_field(
        self,
        df: pd.DataFrame,
        *,
        mode: str | None,
        source_column: str | None,
        text_value: str | None,
        output_column: str,
    ) -> pd.DataFrame:
        out = df.copy()

        if mode == "a":
            if source_column and source_column in out.columns:
                if source_column != output_column:
                    out.rename(columns={source_column: output_column}, inplace=True)
        elif mode == "b":
            out[output_column] = str(text_value or "").strip()

        if output_column == "Weight" and output_column in out.columns:
            out[output_column] = self.normalise_weight_series(out[output_column])

        return out

    def clean_retail_value_series(self, series: pd.Series) -> pd.Series:
        def _clean(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return val
            s = _CURRENCY_RE.sub("", str(val)).strip()
            try:
                n = abs(float(s))
            except (ValueError, TypeError):
                return val
            n = max(1.0, n)
            return int(n) if n == int(n) else n
        return series.map(_clean)

    def populate_missing_town_from_county_or_address(
        self,
        df: pd.DataFrame,
        *,
        town_col: str,
        county_col: str | None,
        postcode_col: str,
        preview_columns: list[str],
    ) -> pd.DataFrame:
        out = df.copy()

        if town_col not in out.columns:
            return out

        county_exists = bool(
            county_col
            and county_col != SENTINEL_SELECT
            and county_col in out.columns
        )
        address_fallback_cols = [
            c
            for c in preview_columns
            if c in out.columns and c not in {town_col, county_col, postcode_col}
        ]

        address1_col = address_fallback_cols[0] if address_fallback_cols else None

        def _blank_mask(series: pd.Series) -> pd.Series:
            na = series.isna()
            s = series.astype(str).str.strip()
            return na | s.eq("") | s.str.lower().eq("nan")

        if address1_col:
            blank_a1 = _blank_mask(out[address1_col])
            for row_index in out.index[blank_a1]:
                for src_col in address_fallback_cols[1:]:
                    src_value = out.at[row_index, src_col]
                    if is_blank(src_value):
                        continue
                    out.at[row_index, address1_col] = src_value
                    out.at[row_index, src_col] = ""
                    break

        blank_town = _blank_mask(out[town_col])
        for row_index in out.index[blank_town]:
            if county_exists:
                county_value = out.at[row_index, county_col]
                if not is_blank(county_value):
                    out.at[row_index, town_col] = county_value
                    out.at[row_index, county_col] = ""
                    continue

            for src_col in reversed(address_fallback_cols):
                src_value = out.at[row_index, src_col]
                if is_blank(src_value):
                    continue

                out.at[row_index, town_col] = src_value
                out.at[row_index, src_col] = ""
                break

        return out

    def multiply_weight_by_quantity(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        if "Weight" not in out.columns or "Quantity" not in out.columns:
            return out

        def to_number(value):
            if pd.isna(value):
                return None
            s = str(value).strip()
            if not s or s.lower() == "nan":
                return None
            try:
                return float(s)
            except ValueError:
                return None

        def fmt_result(weight_raw, qty_raw):
            w = to_number(weight_raw)
            q = to_number(qty_raw)
            if w is None or q is None:
                return "" if pd.isna(weight_raw) else str(weight_raw)
            result = w * q
            return str(int(result)) if float(result).is_integer() else str(result)

        out["Weight"] = [fmt_result(w, q) for w, q in zip(out["Weight"], out["Quantity"])]
        return out

    def apply_recipient_name(
        self,
        df: pd.DataFrame,
        *,
        name_mode: str | None,
        name_column: str | None,
        name_text: str | None,
        surname_mode: str | None,
        surname_column: str | None,
        surname_text: str | None,
    ) -> pd.DataFrame:
        out = df.copy()

        def resolve_series(
            *,
            mode: str | None,
            source_column: str | None,
            text_value: str | None,
        ) -> pd.Series:
            if mode == "a" and source_column and source_column in out.columns:
                return out[source_column].fillna("").astype(str).str.strip()

            if mode == "b":
                value = str(text_value or "").strip()
                return pd.Series([value] * len(out), index=out.index, dtype="object")

            return pd.Series([""] * len(out), index=out.index, dtype="object")

        first = resolve_series(
            mode=name_mode,
            source_column=name_column,
            text_value=name_text,
        )
        last = resolve_series(
            mode=surname_mode,
            source_column=surname_column,
            text_value=surname_text,
        )

        recipient = first.where(last.eq(""), first + " " + last)
        recipient = recipient.fillna("").astype(str).str.strip()

        if "Company" in out.columns:
            company = out["Company"].fillna("").astype(str).str.strip()
            recipient = recipient.where(recipient.ne(""), company)

        out["Recipient Name"] = recipient

        drop_cols: list[str] = []

        if name_mode == "a" and name_column in out.columns and name_column != "Recipient Name":
            drop_cols.append(name_column)

        if surname_mode == "a" and surname_column in out.columns and surname_column != "Recipient Name":
            drop_cols.append(surname_column)

        if drop_cols:
            out.drop(columns=list(dict.fromkeys(drop_cols)), inplace=True)

        return out

    def concat_frames(self, frames: list[pd.DataFrame]) -> pd.DataFrame:
        usable = [f for f in frames if f is not None and not f.empty]
        if not usable:
            return pd.DataFrame()
        return pd.concat(usable, ignore_index=True, sort=False)

    def return_address_output_map(self, row: dict[str, Any]) -> dict[str, str]:
        return {
            "Return Contact Name": coerce_str(row.get("contact_name")),
            "Return Address 1":    coerce_str(row.get("address1")),
            "Return Address 2":    coerce_str(row.get("address2")),
            "Return Address 3":    coerce_str(row.get("address3")),
            "Return Town":         coerce_str(row.get("Town")),
            "Return County":       coerce_str(row.get("County")),
            "Return Postcode":     coerce_str(row.get("postcode")),
        }

    def apply_return_address(
        self,
        df: pd.DataFrame,
        *,
        selected_return_address: str | None,
        return_addresses_repo: ReturnAddressesRepository,
    ) -> pd.DataFrame:
        selected = str(selected_return_address or "").strip()
        if not selected or selected == SENTINEL_SELECT:
            return df

        if selected in self._return_address_cache:
            chosen = self._return_address_cache[selected]
        else:
            matches = return_addresses_repo.search(selected, limit=100000)
            chosen = next(
                (
                    row
                    for row in matches
                    if str(row.get("contact_name", "")).strip() == selected
                ),
                None,
            )
            self._return_address_cache[selected] = chosen

        if chosen is None:
            return df

        out = df.copy()
        values = self.return_address_output_map(chosen)

        for col_name, value in values.items():
            out[col_name] = value

        return out