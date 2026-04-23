from __future__ import annotations

from typing import Any

import pandas as pd


class EcommercePafResolution:
    def __init__(self, transforms):
        self.transforms = transforms

    def collect_resolution_state(self,prepared_df: pd.DataFrame,*,postcode_col: str,town_col: str,preview_specs: list[dict[str, str]],postcodes_repo) -> dict[str, Any]:
        collapsed_postcodes = self.transforms.collapse_postcode_series(prepared_df[postcode_col])
        unique_vals = {v for v in collapsed_postcodes.tolist() if v}

        existing = postcodes_repo.existing_postcode_set(unique_vals)
        matched_mask = collapsed_postcodes.isin(existing)

        town_series = self.transforms.collapse_text_series(prepared_df[town_col])
        town_missing_mask = town_series.eq("") | town_series.str.lower().eq("nan")

        paf_address1_source = next(
            (spec.get("source")for spec in preview_specs if str(spec.get("paf", "")).strip() == "PAF Address 1"), None)

        if paf_address1_source and paf_address1_source in prepared_df.columns:
            address1_series = self.transforms.collapse_text_series(prepared_df[paf_address1_source])
            address1_missing_mask = address1_series.eq("") | address1_series.str.lower().eq("nan")
        else:
            address1_missing_mask = pd.Series([False] * len(prepared_df), index=prepared_df.index)

        resolution_mask = (~matched_mask) | town_missing_mask | address1_missing_mask
        resolution_df = prepared_df.loc[resolution_mask].copy()
        resolution_postcodes = collapsed_postcodes[resolution_mask].tolist()
        resolution_indices = list(prepared_df[resolution_mask].index)

        issue_labels: list[str] = []
        for row_index in resolution_indices:
            reasons = []
            if not bool(matched_mask.loc[row_index]):
                reasons.append("Postcode not found")
            if bool(town_missing_mask.loc[row_index]):
                reasons.append("Town missing")
            if bool(address1_missing_mask.loc[row_index]):
                reasons.append("Address line 1 missing")
            issue_labels.append(", ".join(reasons) if reasons else "Review")

        row_previews: list[dict[str, str]] = []
        if preview_specs:
            preview_df = pd.DataFrame(index=resolution_df.index)
            for spec in preview_specs:
                src, dst = spec["source"], spec["preview"]
                if src in resolution_df.columns:
                    preview_df[dst] = resolution_df[src].fillna("").astype(str)
                else:
                    preview_df[dst] = ""
            row_previews = preview_df.to_dict("records")

        return {"resolution_indices": resolution_indices,"resolution_postcodes": resolution_postcodes,"issue_labels": issue_labels,
                "row_previews": row_previews,"preview_specs": preview_specs}

    def apply_resolution_result(self,prepared_df: pd.DataFrame,*,postcode_col: str,resolution_state: dict[str, Any],
                                resolution_result: dict[str, Any],postcodes_repo,logger=None) -> tuple[pd.DataFrame, pd.DataFrame]:
        working_df = prepared_df.copy()
        paf_reject_rows = []

        resolution_indices = resolution_state["resolution_indices"]
        corrected = resolution_result["corrected"]
        added = resolution_result["added"]
        removed = resolution_result["removed"]
        row_updates = resolution_result["row_updates"]

        for i, row_index in enumerate(resolution_indices):
            if row_index not in working_df.index:
                continue

            if i in removed:
                paf_reject_rows.append(working_df.loc[row_index].copy())
                working_df.drop(index=row_index, inplace=True)
                continue

            updates = row_updates.get(i, {})
            for col, value in updates.items():
                if col in working_df.columns:
                    working_df.loc[row_index, col] = value

            if i in corrected:
                working_df.loc[row_index, postcode_col] = corrected[i]
                continue

            if i in added:
                working_df.loc[row_index, postcode_col] = added[i]
                try:
                    postcodes_repo.insert_postcode(added[i])
                except Exception as e:
                    if logger:
                        logger.log(f"[PAF] Failed to save postcode '{added[i]}' to database: {e}", "red")
                continue
        working_df.reset_index(drop=True, inplace=True)

        paf_reject_df = pd.DataFrame(paf_reject_rows)
        if not paf_reject_df.empty:
            paf_reject_df.reset_index(drop=True, inplace=True)

        return working_df, paf_reject_df