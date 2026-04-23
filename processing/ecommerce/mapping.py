from __future__ import annotations

import pandas as pd

from config.constants import PAF_COUNTY_COL, PAF_POSTCODE_COL, PAF_TOWN_COL, SENTINEL_SELECT

class EcommerceMapping:
    def build_preview_columns(self,*,all_columns: list[str],address_start: str | None,address_end: str |
                              None,town_col: str | None,county_col: str | None,postcode_col: str,) -> list[str]:
        address_columns: list[str] = []
        if (address_start and address_end and address_start != SENTINEL_SELECT and address_end != SENTINEL_SELECT and address_start in all_columns and address_end in all_columns):
            start_idx = all_columns.index(address_start)
            end_idx = all_columns.index(address_end)

            if start_idx > end_idx:
                raise ValueError("Address start must come before Address end.")

            address_columns = all_columns[start_idx : end_idx + 1]

        special_cols = [c for c in [town_col, county_col, postcode_col] if c and c != SENTINEL_SELECT]
        base_address_columns = [c for c in address_columns if c not in special_cols]

        preview_columns = list(base_address_columns)

        if town_col and town_col != SENTINEL_SELECT and town_col not in preview_columns:
            preview_columns.append(town_col)

        if county_col and county_col != SENTINEL_SELECT and county_col not in preview_columns:
            preview_columns.append(county_col)

        if postcode_col and postcode_col != SENTINEL_SELECT and postcode_col not in preview_columns:
            preview_columns.append(postcode_col)

        return preview_columns

    def build_paf_name_map(self,*,preview_columns: list[str],town_col: str | None,county_col: str | None,postcode_col: str) -> dict[str, str]:
        name_map: dict[str, str] = {}

        address_idx = 1
        for col in preview_columns:
            if col == town_col:
                name_map[col] = PAF_TOWN_COL
            elif col == county_col:
                name_map[col] = PAF_COUNTY_COL
            elif col == postcode_col:
                name_map[col] = PAF_POSTCODE_COL
            else:
                name_map[col] = f"PAF Address {address_idx}"
                address_idx += 1

        return name_map

    def build_preview_specs(self,*,preview_columns: list[str],town_col: str | None,county_col: str | None,postcode_col: str,) -> list[dict[str, str]]:
        paf_name_map = self.build_paf_name_map(preview_columns=preview_columns,town_col=town_col,county_col=county_col,postcode_col=postcode_col,)

        specs: list[dict[str, str]] = []
        for src_col in preview_columns:
            paf_name = paf_name_map[src_col]
            specs.append({"source": src_col,"paf": paf_name,"preview": f"{paf_name} (Preview)",})
        return specs

    def rename_to_paf_columns(self,df: pd.DataFrame,*,preview_columns: list[str],town_col: str | None,county_col: str | None,postcode_col: str,) -> pd.DataFrame:
        out = df.copy()
        rename_map = self.build_paf_name_map(preview_columns=preview_columns,town_col=town_col,county_col=county_col,postcode_col=postcode_col)
        out.rename(columns=rename_map, inplace=True)
        return out

    def sorted_paf_address_columns(self, columns: list[str]) -> list[str]:
        def sort_key(col: str) -> tuple[int, str]:
            text = str(col)
            prefix = "PAF Address "
            if text.startswith(prefix):
                suffix = text[len(prefix):].strip()
                try:
                    return (0, int(suffix))
                except ValueError:
                    return (0, 999999)
            return (1, text.lower())

        return sorted([str(c) for c in columns if str(c).startswith("PAF Address ")], key=sort_key)

    def order_ecommerce_output_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        out = df.copy()
        cols = [str(c) for c in out.columns]

        ordered: list[str] = []

        def add(col: str):
            if col in out.columns and col not in ordered:
                ordered.append(col)

        leading_fixed = ["Client Item Reference","Recipient Name","Company",]

        service_block = ["Service","Weight","Length","Width","Height","Country Code","Quantity","Product Description","Retail Value",]

        return_address_block = ["Return Contact Name","Return Address 1","Return Address 2","Return Address 3","Return Town","Return Postcode",]

        for col in leading_fixed:
            add(col)

        for col in self.sorted_paf_address_columns(cols):
            add(col)

        add(PAF_TOWN_COL)
        add(PAF_COUNTY_COL)
        add(PAF_POSTCODE_COL)

        reserved = set(ordered) | set(service_block) | set(return_address_block)

        middle = [c for c in out.columns if c not in reserved]
        ordered.extend(middle)

        for col in service_block:
            add(col)

        for col in return_address_block:
            add(col)

        for col in out.columns:
            if col not in ordered:
                ordered.append(col)

        return out.loc[:, ordered]