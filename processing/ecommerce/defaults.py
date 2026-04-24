from __future__ import annotations

import re
from typing import Any

from config.constants import ECOMMERCE_HEADER_SYNONYMS

class EcommerceDefaults:
    def norm_header(self, text: str) -> str:
        s = str(text or "").strip().lower()
        s = re.sub(r"[_\-.]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def norm_compact(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", self.norm_header(text))

    def best_header_match(self, columns: list[str], aliases: list[str]) -> str | None:
        if not columns or not aliases:
            return None

        exact_map = {self.norm_header(c): c for c in columns}
        compact_map = {self.norm_compact(c): c for c in columns}

        alias_norms = [self.norm_header(a) for a in aliases]
        alias_compacts = [self.norm_compact(a) for a in aliases]

        for alias in alias_norms:
            if alias in exact_map:
                return exact_map[alias]

        for alias in alias_compacts:
            if alias in compact_map:
                return compact_map[alias]

        for alias in alias_norms:
            for col in columns:
                nc = self.norm_header(col)
                if alias and (nc.startswith(alias) or alias in nc):
                    return col

        for alias in alias_compacts:
            for col in columns:
                cc = self.norm_compact(col)
                if alias and (cc.startswith(alias) or alias in cc):
                    return col

        return None

    def detect_address_like_columns(self, columns: list[str]) -> list[str]:
        found: list[tuple[int, str]] = []

        for i, col in enumerate(columns):
            nh = self.norm_header(col)
            nc = self.norm_compact(col)

            is_address = False

            if re.search(r"\b(address|addr|add|line)\s*([1-9])\b", nh):
                is_address = True

            if re.search(r"(address|addr|add|line)([1-9])\b", nc):
                is_address = True

            if re.fullmatch(r"a[1-9]", nc):
                is_address = True

            if "address" in nh and re.search(r"\b[1-9]\b", nh):
                is_address = True

            if is_address:
                found.append((i, col))

        found.sort(key=lambda x: x[0])
        return [col for _, col in found]

    def detect_address_range(self,columns: list[str],*,town_col: str | None = None,county_col: str | None = None,
                             postcode_col: str | None = None,) -> tuple[str | None, str | None]:
        candidates: list[str] = []
        address_cols = self.detect_address_like_columns(columns)
        candidates.extend(address_cols)

        for col in (town_col, county_col, postcode_col):
            if col and col in columns:
                candidates.append(col)

        candidates = list(dict.fromkeys(candidates))
        if not candidates:
            return None, None

        positions = [(columns.index(col), col) for col in candidates if col in columns]
        if not positions:
            return None, None

        positions.sort(key=lambda x: x[0])
        return positions[0][1], positions[-1][1]

    @staticmethod
    def _is_automap_blacklisted(column_name: str) -> bool:
        return "return" in str(column_name).strip().lower()

    def detect_ecommerce_defaults(self, columns: list[str]) -> dict[str, Any]:
        # Exclude return-address columns so they are never auto-mapped into
        # delivery address / town / postcode / service fields.
        eligible = [c for c in columns if not self._is_automap_blacklisted(c)]

        defaults: dict[str, Any] = {}

        for target_key, aliases in ECOMMERCE_HEADER_SYNONYMS.items():
            match = self.best_header_match(eligible, aliases)
            if match:
                defaults[target_key] = match

        start, end = self.detect_address_range(eligible,town_col=defaults.get("town_column"),county_col=defaults.get("county_column"),
                                               postcode_col=defaults.get("postcode_column"),)
        if start:
            defaults["address_start"] = start
        if end:
            defaults["address_end"] = end

        return defaults

    def apply_schema_defaults(self, schema: list[dict], defaults: dict[str, Any]) -> None:
        def visit(cfg: dict) -> None:
            key = cfg.get("key")
            if key in defaults:
                cfg["default"] = defaults[key]

            if cfg.get("type") == "range_select":
                start_key = cfg.get("start_key")
                end_key = cfg.get("end_key")
                if start_key in defaults:
                    cfg["default_start"] = defaults[start_key]
                if end_key in defaults:
                    cfg["default_end"] = defaults[end_key]

            for child in cfg.get("children", []) or []:
                if isinstance(child, dict):
                    visit(child)

            for child_key in ("control_a", "control_b"):
                child_cfg = cfg.get(child_key)
                if isinstance(child_cfg, dict):
                    visit(child_cfg)

        for item in schema:
            visit(item)