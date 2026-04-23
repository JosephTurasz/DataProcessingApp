from __future__ import annotations

from PySide6.QtWidgets import QLabel

from config.constants import SENTINEL_SELECT

class DialogRules:
    def __init__(self, ctx, schema, ok_button_getter):
        self.ctx = ctx
        self.schema = schema
        self._ok_button_getter = ok_button_getter

        self._item_split_total: int | None = None
        self._syncing_item_split: bool = False

    def rule_matches(self, rule: dict) -> bool:
        if not rule:
            return True

        dep_key = rule.get("key")
        op = (rule.get("op") or "==").strip()
        rhs = rule.get("value")
        lhs = self.ctx.get(dep_key)

        try:
            if op == "==":
                return lhs == rhs
            if op == "!=":
                return lhs != rhs
            if op == "<=":
                return lhs <= rhs
            if op == "<":
                return lhs < rhs
            if op == ">=":
                return lhs >= rhs
            if op == ">":
                return lhs > rhs
        except Exception:
            return False

        return False

    def cfg_is_currently_required(self, cfg: dict) -> bool:
        if bool(cfg.get("always_required", False)):
            return True

        required_if = cfg.get("required_if")
        if required_if:
            return self.rule_matches(required_if)

        return bool(cfg.get("required", False))

    def refresh_visibility(self) -> None:
        for cfg in self.schema:
            self._refresh_cfg_visibility(cfg)

    def _refresh_cfg_visibility(self, cfg: dict) -> None:
        cfg_type = str(cfg.get("type", ""))

        if cfg_type in {"section", "compact_select_row"}:
            for child in cfg.get("children", []):
                self._refresh_cfg_visibility(child)

        key = cfg.get("key")
        if not key:
            return

        widget = self.ctx.widget_for(key)
        if widget is None:
            return

        visible_if = cfg.get("visible_if")
        widget.setVisible(True if not visible_if else bool(self.rule_matches(visible_if)))

    def refresh_switch_labels(self, cfg: dict) -> None:
        cfg_type = str(cfg.get("type", ""))

        if cfg_type in {"section", "compact_select_row"}:
            for child in cfg.get("children", []):
                self.refresh_switch_labels(child)
            return

        if cfg_type != "switch_with_extras":
            return

        binding = self.ctx.binding(str(cfg.get("key", "")))
        if binding is None or binding.widget is None:
            return

        label = getattr(binding.widget, "_switch_label", None)
        if label is None:
            label = binding.widget.findChild(QLabel)
        if label is None:
            return

        mode = binding.get_value()
        base_field_name = str(cfg.get("field_name", "")).strip()
        required_now = self.cfg_is_currently_required(cfg)
        suffix = "*" if required_now else ""

        if base_field_name:
            label.setText(
                f"Enter {base_field_name}{suffix}" if mode == "b"
                else f"Select {base_field_name}{suffix}"
            )

    def refresh_required_state(self) -> None:
        ok_button = self._ok_button_getter()
        if ok_button is None:
            return

        required_keys = set(self.ctx.required_keys)

        for cfg in self.schema:
            self._collect_switch_required_keys(cfg, required_keys)

        if bool(self.ctx.get("use_max_service_dimensions")):
            for prefix in ("length", "width", "height"):
                required_keys.discard(f"{prefix}_column")
                required_keys.discard(f"{prefix}_text")

        for key in required_keys:
            if self._is_missing_required_value(self.ctx.get(key)):
                ok_button.setEnabled(False)
                return

        ok_button.setEnabled(True)

    def _is_missing_required_value(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() in ("", SENTINEL_SELECT)
        return False

    def _required_keys_for_switch_with_extras(self, cfg: dict) -> list[str]:
        required_if = cfg.get("required_if")
        mode_map = cfg.get("required_mode_map") or {}

        if not mode_map:
            return []

        if required_if and not self.rule_matches(required_if):
            return []

        mode_key = str(cfg.get("key", "")).strip()
        if not mode_key:
            return []

        mode_binding = self.ctx.binding(mode_key)
        if mode_binding is None:
            return []

        mode = mode_binding.get_value()
        keys = mode_map.get(mode, [])
        return [str(k) for k in keys if k]

    def _collect_switch_required_keys(self, cfg: dict, out: set[str]) -> None:
        cfg_type = str(cfg.get("type", ""))

        if cfg_type in {"section", "compact_select_row"}:
            for child in cfg.get("children", []):
                self._collect_switch_required_keys(child, out)
            return

        if cfg_type == "switch_with_extras":
            control_a = cfg.get("control_a") or {}
            control_b = cfg.get("control_b") or {}

            key_a = str(control_a.get("key", "")).strip()
            key_b = str(control_b.get("key", "")).strip()

            if key_a:
                out.discard(key_a)
            if key_b:
                out.discard(key_b)

            for key in self._required_keys_for_switch_with_extras(cfg):
                out.add(key)
                
    def sync_item_split_numbers(self, changed_key: str) -> None:
        if self._syncing_item_split:
            return
        if self._item_split_total is None:
            return

        spin1 = self.ctx.number_widgets.get("items_file1")
        spin2 = self.ctx.number_widgets.get("items_file2")
        if spin1 is None or spin2 is None:
            return

        total = int(self._item_split_total)

        def clamp(value: int) -> int:
            if value < 0:
                return 0
            if value > total:
                return total
            return value

        try:
            self._syncing_item_split = True

            if changed_key == "items_file2":
                v2 = clamp(int(spin2.value()))
                v1 = clamp(total - v2)
                v2 = clamp(total - v1)
            else:
                v1 = clamp(int(spin1.value()))
                v2 = clamp(total - v1)
                v1 = clamp(total - v2)

            if spin1.value() != v1:
                spin1.blockSignals(True)
                spin1.setValue(int(v1))
                spin1.blockSignals(False)

            if spin2.value() != v2:
                spin2.blockSignals(True)
                spin2.setValue(int(v2))
                spin2.blockSignals(False)

        finally:
            self._syncing_item_split = False
            
    def set_item_split_total(self, value: int | None) -> None:
        try:
            self._item_split_total = int(value) if value is not None else None
        except Exception:
            self._item_split_total = None