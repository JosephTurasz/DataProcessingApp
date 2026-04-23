from __future__ import annotations

from typing import Any

from config.constants import SENTINEL_SELECT

from PySide6.QtWidgets import QCheckBox, QLabel, QComboBox, QStackedLayout

from gui.options_engine.bindings import ControlBinding

class DialogMutexController:
    def __init__(self, ctx, iter_options):
        self.ctx = ctx
        self._iter_options = iter_options

    def binding_is_mutex_active(self, binding: ControlBinding) -> bool:
        cfg = binding.cfg or {}
        parent_mode_key = cfg.get("parent_mode_key")
        active_mode_value = cfg.get("active_mode_value")
        if not parent_mode_key:
            return True
        return self.ctx.get(parent_mode_key) == active_mode_value

    def refresh_group(self, group: str) -> None:
        keys = [str(k) for k in self.ctx.mutex_groups.get(str(group), [])]
        if not keys:
            return
        group_rows: dict[str, dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]]] = {}
        selected_by_key: dict[str, set[Any]] = {}

        for key in keys:
            rows = self.ctx.multi_rows.get(key) or {}
            group_rows[key] = rows
            selected_by_key[key] = {value for value, (cb, _x, _stack) in rows.items() if cb.isChecked()}

        for key in keys:
            rows = group_rows.get(key, {})
            selected_elsewhere: set[Any] = set()
            for other_key, selected_values in selected_by_key.items():
                if other_key != key:
                    selected_elsewhere.update(selected_values)
            for value, (cb, x_lbl, stack) in rows.items():
                is_selected_here = cb.isChecked()
                blocked_elsewhere = value in selected_elsewhere
                should_enable = is_selected_here or not blocked_elsewhere
                cb.setEnabled(should_enable)
                stack.setCurrentWidget(x_lbl if blocked_elsewhere and not is_selected_here else cb)

    def refresh_selects(self) -> None:
        groups: dict[str, list[ControlBinding]] = {}
        for binding in self.ctx.bindings.values():
            cfg = binding.cfg or {}
            group = cfg.get("mutex_group")
            if group:
                groups.setdefault(str(group), []).append(binding)

        for bindings in groups.values():
            selected_values: dict[str, object] = {}
            for binding in bindings:
                if not self.binding_is_mutex_active(binding):
                    continue
                value = binding.get_value()
                if value not in (None, "", SENTINEL_SELECT):
                    selected_values[str(binding.key)] = value

            for binding in bindings:
                cfg = binding.cfg or {}
                options = cfg.get("options") or []
                current_value = binding.get_value()
                widget = binding.widget
                combo = widget if isinstance(widget, QComboBox) else widget.findChild(QComboBox)
                if combo is None:
                    continue
                
                blocked = {v for k, v in selected_values.items() if k != str(binding.key)}
                filtered = []
                for label, value in self._iter_options(options):
                    if value == SENTINEL_SELECT or value == current_value or value not in blocked:
                        filtered.append((label, value))

                if current_value in blocked:
                    current_value = SENTINEL_SELECT

                combo.blockSignals(True)
                combo.clear()

                for label, value in filtered:
                    combo.addItem(label, value)

                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    idx = combo.findData(SENTINEL_SELECT)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                combo.blockSignals(False)