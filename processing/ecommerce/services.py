from __future__ import annotations

from typing import Any

import pandas as pd

from config.constants import MAX_SERVICE_DIMENSIONS, DEFAULT_WINDSOR_DETAILS
from processing.repos.ecom_services_repo import EcomServicesRepository
from utils.value_utils import coerce_str, is_blank, normalize_code

class EcommerceServices:
    def __init__(self):
        self._rule_maps_cache: tuple[dict, dict] | None = None

    def to_float_or_none(self, value) -> float | None:
        if isinstance(value, pd.Series):
            non_blank = []
            for item in value.tolist():
                if pd.isna(item):
                    continue
                s = str(item).strip()
                if not s or s.lower() == "nan":
                    continue
                non_blank.append(item)

            if not non_blank:
                return None

            value = non_blank[-1]

        if pd.isna(value):
            return None

        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None

        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def normalise_service_code(self, value) -> str:
        return normalize_code(value)

    def service_rule_maps(self,ecom_services_repo: EcomServicesRepository) -> tuple[dict[str, dict], dict[str, dict]]:
        if self._rule_maps_cache is not None:
            return self._rule_maps_cache

        rows = ecom_services_repo.list_all(limit=100000)

        by_new: dict[str, dict] = {}
        by_old: dict[str, dict] = {}

        for row in rows:
            new_code = self.normalise_service_code(row.get("new_code"))
            old_code = self.normalise_service_code(row.get("old_code"))

            if new_code:
                by_new[new_code] = row
            if old_code:
                by_old[old_code] = row

        self._rule_maps_cache = (by_new, by_old)
        return self._rule_maps_cache

    def service_rule_cache(self,ecom_services_repo: EcomServicesRepository) -> dict[str, Any]:
        by_new, by_old = self.service_rule_maps(ecom_services_repo)
        all_rules = list(by_new.values())

        return {"by_new": by_new,"by_old": by_old,"all_rules": all_rules,}

    def find_service_rule(self,service_value: str,by_new: dict[str, dict],by_old: dict[str, dict]) -> dict | None:
        key = self.normalise_service_code(service_value)
        if not key:
            return None
        return by_new.get(key) or by_old.get(key)

    def canonical_service_code_from_rule(self,rule: dict | None,fallback: str = "") -> str:
        if not rule:
            return self.normalise_service_code(fallback)

        replacement_code = self.normalise_service_code(rule.get("replacement_code"))
        if replacement_code:
            return replacement_code

        new_code = self.normalise_service_code(rule.get("new_code"))
        if new_code:
            return new_code

        old_code = self.normalise_service_code(rule.get("old_code"))
        if old_code:
            return old_code

        return self.normalise_service_code(fallback)

    def canonicalise_service_value(self,service_value,*,by_new: dict[str, dict],by_old: dict[str, dict]) -> str:
        original = coerce_str(service_value)
        rule = self.find_service_rule(original, by_new, by_old)
        return self.canonical_service_code_from_rule(rule, fallback=original)

    def service_fits_rule(self,*,length_value,width_value,height_value,weight_value,rule: dict) -> bool:
        length = self.to_float_or_none(length_value)
        width = self.to_float_or_none(width_value)
        height = self.to_float_or_none(height_value)
        weight = self.to_float_or_none(weight_value)

        min_length = self.to_float_or_none(rule.get("min_length_mm"))
        min_width = self.to_float_or_none(rule.get("min_width_mm"))
        min_height = self.to_float_or_none(rule.get("min_height_mm"))

        max_length = self.to_float_or_none(rule.get("max_length_mm"))
        max_width = self.to_float_or_none(rule.get("max_width_mm"))
        max_height = self.to_float_or_none(rule.get("max_height_mm"))
        max_weight = self.to_float_or_none(rule.get("max_weight_g"))

        dimension_pairs = [(length, min_length, max_length),(width, min_width, max_width),(height, min_height, max_height)]

        for value, min_v, max_v in dimension_pairs:
            if value is None:
                continue
            if min_v is not None and value < min_v:
                return False
            if max_v is not None and value > max_v:
                return False

        if weight is not None and max_weight is not None and weight > max_weight:
            return False

        return True

    def service_display_code(self, rule: dict) -> str:
        return self.canonical_service_code_from_rule(rule)

    def service_reject_reason(self,*,service_value,length_value,width_value,height_value,weight_value,by_new: dict[str, dict],by_old: dict[str, dict]) -> str | None:
        rule = self.find_service_rule(service_value, by_new, by_old)
        if rule is None:
            return "Invalid Service"

        if not self.service_fits_rule(length_value=length_value,width_value=width_value,height_value=height_value,weight_value=weight_value,rule=rule,):
            max_weight = self.to_float_or_none(rule.get("max_weight_g"))
            weight = self.to_float_or_none(weight_value)
            if weight is not None and max_weight is not None and weight > max_weight:
                return "Too Heavy For Selected Service"
            return "Outside Selected Service Dimensions"

        return None

    def valid_services_for_rows(self,rows: list[dict[str, Any]],*,all_rules: list[dict],) -> list[str]:
        valid_codes: list[str] = []
        seen: set[str] = set()

        for rule in all_rules:
            code = self.service_display_code(rule)
            if not code or code in seen:
                continue

            for row in rows:
                if self.service_fits_rule(length_value=row.get("Length"),width_value=row.get("Width"),height_value=row.get("Height"),weight_value=row.get("Weight"),rule=rule,):
                    seen.add(code)
                    valid_codes.append(code)
                    break

        valid_codes.sort()
        return valid_codes

    def apply_max_service_dimensions(self,df: pd.DataFrame,*,ecom_services_repo: EcomServicesRepository,service_column: str = "Service",) -> pd.DataFrame:
        out = df.copy()

        if service_column not in out.columns:
            return out

        by_new, by_old = self.service_rule_maps(ecom_services_repo)

        def scalar_text(row, col: str) -> str:
            value = row.get(col, "")
            if isinstance(value, pd.Series):
                non_blank = [str(item).strip() for item in value.tolist() if not is_blank(item)]
                return non_blank[-1] if non_blank else ""
            return coerce_str(value)

        def fallback_dimension(column_name: str, existing_value: str) -> str:
            fallback = str(MAX_SERVICE_DIMENSIONS.get(column_name, "") or "").strip()
            return fallback or existing_value

        def rule_or_fallback(rule_value, column_name: str, existing_value: str) -> str:
            if pd.isna(rule_value):
                return fallback_dimension(column_name, existing_value)

            text = str(rule_value).strip()
            if text:
                return text

            return fallback_dimension(column_name, existing_value)

        svc_strs = out[service_column].map(coerce_str).tolist()
        rules = [self.find_service_rule(v, by_new, by_old) for v in svc_strs]

        existing_lengths = out["Length"].map(coerce_str).tolist() if "Length" in out.columns else [""] * len(out)
        existing_widths  = out["Width"].map(coerce_str).tolist() if "Width" in out.columns else [""] * len(out)
        existing_heights = out["Height"].map(coerce_str).tolist() if "Height" in out.columns else [""] * len(out)

        out["Length"] = [ex if r is None else rule_or_fallback(r.get("max_length_mm"), "Length", ex) for r, ex in zip(rules, existing_lengths)]
        out["Width"]  = [ex if r is None else rule_or_fallback(r.get("max_width_mm"),  "Width",  ex) for r, ex in zip(rules, existing_widths)]
        out["Height"] = [ex if r is None else rule_or_fallback(r.get("max_height_mm"), "Height", ex) for r, ex in zip(rules, existing_heights)]
        return out

    def use_replacement_service_code(self,df: pd.DataFrame,*,ecom_services_repo: EcomServicesRepository,service_column: str = "Service",) -> pd.DataFrame:
        out = df.copy()

        if service_column not in out.columns:
            return out
        by_new, by_old = self.service_rule_maps(ecom_services_repo)
        out[service_column] = out[service_column].map(lambda value: self.canonicalise_service_value(value,by_new=by_new,by_old=by_old))
        return out

    def collect_service_resolution_state(self,df: pd.DataFrame,*,rule_cache: dict[str, Any],) -> dict[str, Any]:
        by_new = rule_cache["by_new"]
        by_old = rule_cache["by_old"]

        required_cols = ["Length", "Width", "Height", "Weight", "Service"]
        for col in required_cols:
            if col not in df.columns:
                return {"resolution_indices": [], "rows": [], "valid_services": []}

        reject_reasons = df.apply(
            lambda row: self.service_reject_reason(
                service_value=row.get("Service"), length_value=row.get("Length"),
                width_value=row.get("Width"), height_value=row.get("Height"),
                weight_value=row.get("Weight"), by_new=by_new, by_old=by_old,
            ),
            axis=1,
        )
        reject_mask = reject_reasons.notna()

        resolution_indices = [int(i) for i in df.index[reject_mask]]
        reject_subset = df.loc[reject_mask, required_cols].fillna("").astype(str)
        reject_subset["Reject Reason"] = reject_reasons[reject_mask].values
        rows = reject_subset.to_dict("records")

        valid_services = self.valid_services_for_rows(rows, all_rules=rule_cache["all_rules"])
        return {"resolution_indices": resolution_indices, "rows": rows, "valid_services": valid_services}

    def apply_service_resolution_result(self,df: pd.DataFrame,*,resolution_indices: list[int],result: dict[str, Any],
                                        use_max_service_dimensions: bool = False,ecom_services_repo: EcomServicesRepository,) -> pd.DataFrame:
        out = df.copy()
        edited_rows = list(result.get("rows", []) or [])
        original_rows = list(result.get("original_rows", []) or [])
        mass_update = dict(result.get("mass_update") or {})

        by_new, by_old = self.service_rule_maps(ecom_services_repo)

        if use_max_service_dimensions:
            bulk_fields = ("Weight", "Service")
        else:
            bulk_fields = ("Length", "Width", "Height", "Weight", "Service")

        for pos, idx in enumerate(resolution_indices):
            if idx not in out.index:
                continue

            edited = edited_rows[pos] if pos < len(edited_rows) else {}
            original = original_rows[pos] if pos < len(original_rows) else {}

            for col in bulk_fields:
                if col not in out.columns:
                    continue

                current_value = out.loc[idx, col]

                bulk_value = mass_update.get(col, "")
                bulk_value = coerce_str(bulk_value)

                original_value = original.get(col, "")
                original_value = coerce_str(original_value)

                edited_value = edited.get(col, "")
                edited_value = coerce_str(edited_value)

                value_to_write = current_value

                if bulk_value:
                    value_to_write = bulk_value

                if edited_value != original_value:
                    value_to_write = edited_value

                if col == "Service":
                    value_to_write = self.canonicalise_service_value(value_to_write,by_new=by_new,by_old=by_old)

                out.loc[idx, col] = value_to_write

        if use_max_service_dimensions:
            out = self.apply_max_service_dimensions(out,ecom_services_repo=ecom_services_repo,service_column="Service",)

        return out

    def split_valid_and_service_rejects(self,df: pd.DataFrame,*,ecom_services_repo: EcomServicesRepository) -> tuple[pd.DataFrame, pd.DataFrame]:
        by_new, by_old = self.service_rule_maps(ecom_services_repo)

        reject_reasons = df.apply(
            lambda row: self.service_reject_reason(
                service_value=row.get("Service"), length_value=row.get("Length"),
                width_value=row.get("Width"), height_value=row.get("Height"),
                weight_value=row.get("Weight"), by_new=by_new, by_old=by_old,
            ),
            axis=1,
        )
        reject_mask = reject_reasons.notna()

        valid_df = df.loc[~reject_mask].copy().reset_index(drop=True)

        reject_df = df.loc[reject_mask].copy()
        reject_df["Reject Reason"] = reject_reasons[reject_mask].values
        reject_df.reset_index(drop=True, inplace=True)

        return valid_df, reject_df

    def apply_default_windsor_details(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        for col, value in DEFAULT_WINDSOR_DETAILS.items():
            out[col] = value

        return out