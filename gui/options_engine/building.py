from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Tuple

from config.constants import SENTINEL_SELECT

from gui.toggle_switch import ToggleSwitch
from gui.options_engine.bindings import ExtrasBinding, ControlBinding, DynamicMultiBinding

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QRadioButton, QButtonGroup, QComboBox,QLineEdit,QLabel,QGroupBox,QScrollArea,
                               QCheckBox,QFrame,QStyle,QStackedLayout,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QSpinBox)

class DialogBuilder:
    def __init__(self,ctx,rules,mutex=None,refresh_all: Callable[[], None] | None = None,sync_item_split_numbers: Callable[[str], None] | None = None,):
        self.ctx = ctx
        self.rules = rules
        self.mutex = mutex
        self.refresh_all = refresh_all or (lambda: None)
        self.sync_item_split_numbers = sync_item_split_numbers or (lambda _key: None)

        self._builders = {
            "radio": self._build_radio,
            "radio_with_extras": self._build_radio_with_extras,
            "radio_with_shared_extras": self._build_radio_with_shared_extras,
            "select": self._build_select,
            "text": self._build_text,
            "compact_select": self._build_compact_select,
            "compact_select_row": self._build_compact_select_row,
            "labeled_select_row": self._build_labeled_select_row,
            "toggle_select": self._build_toggle_select,
            "switch_with_extras": self._build_switch_with_extras,
            "multi_select": self._build_multi_select,
            "number": self._build_number,
            "range_select": self._build_range_select,
            "table_preview": self._build_table_preview,
            "section": self._build_section,
            "checkbox": self._build_checkbox,
        }

    def build(self, cfg: dict) -> QWidget:
        kind = cfg.get("type")
        builder = self._builders.get(kind)
        if not builder:
            raise ValueError(f"Unsupported schema type: {kind!r}")
        return builder(cfg)

    def _build_extras_controller(self,*,base_layout,extras_cfg: dict,
                                 is_enabled_fn: Callable[[], bool],
                                 get_value_fn: Callable[[], Any],
                                 layout_override: Optional[dict] = None
                                 ) -> ExtrasBinding:
        widgets_by_option: dict[Any, list[tuple[str, QWidget]]] = {}

        for opt_value, extras in (extras_cfg or {}).items():
            widgets: list[tuple[str, QWidget]] = []
            target_layout = layout_override.get(opt_value, base_layout) if layout_override else base_layout

            for extra in extras if isinstance(extras, list) else [extras]:
                etype = extra.get("type")

                if etype == "text":
                    row = QHBoxLayout()
                    row.addWidget(QLabel(extra.get("label", "")))

                    edit = QLineEdit()
                    edit.setText(str(extra.get("default", "")))
                    edit.setEnabled(False)

                    placeholder = extra.get("placeholder")
                    if placeholder is not None:
                        edit.setPlaceholderText(str(placeholder))

                    row.addWidget(edit)
                    target_layout.addLayout(row)
                    widgets.append((extra["key"], edit))
                    edit.textChanged.connect(self.refresh_all)

                elif etype == "select":
                    row = QHBoxLayout()
                    row.addWidget(QLabel(extra.get("label", "")))

                    combo = self._make_combo(
                        options=extra.get("options") or [],
                        default=extra.get("default"),
                        enabled=False,
                        visible=True)
                    row.addWidget(combo)
                    target_layout.addLayout(row)
                    widgets.append((extra["key"], combo))
                    combo.currentIndexChanged.connect(self.refresh_all)

                else:
                    raise ValueError(f"Unsupported extra type: {etype!r}")

            widgets_by_option[opt_value] = widgets

        return ExtrasBinding(
            widgets_by_option=widgets_by_option,
            enabled_when=is_enabled_fn,
            selected_value=get_value_fn)

    def _build_text(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            layout.addWidget(QLabel(label_text))

        edit = QLineEdit()
        edit.setText(str(cfg.get("default", "")))
        edit.setFixedHeight(24)
        edit.setFixedWidth(220)

        placeholder = cfg.get("placeholder")
        if placeholder is not None:
            edit.setPlaceholderText(str(placeholder))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(edit)
        row.addStretch()
        layout.addLayout(row)

        self._register_binding(cfg["key"], container, lambda: edit.text().strip(), cfg)
        edit.textChanged.connect(self.refresh_all)
        return container

    def _build_radio(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        default_value = cfg.get("default")

        radios, get_selected = self._make_radio_group(
            parent_layout=layout,
            options=cfg.get("options", []),
            default=default_value,
            orientation="horizontal")

        def reset():
            for rb in radios:
                rb.blockSignals(True)
                rb.setChecked(rb._value == default_value)
                rb.blockSignals(False)

        self._register_binding(cfg["key"], box, get_selected, cfg, reset_to_default=reset)

        for rb in radios:
            rb.toggled.connect(self.refresh_all)

        return box

    def _build_radio_with_extras(self, cfg: dict) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            outer.addWidget(QLabel(label_text))

        orientation = str(cfg.get("orientation", "vertical")).lower()
        radio_row = QHBoxLayout() if orientation == "horizontal" else QVBoxLayout()
        radio_row.setContentsMargins(0, 0, 0, 0)
        radio_row.setSpacing(10 if orientation == "horizontal" else 4)

        button_group = QButtonGroup(container)
        buttons_by_value: dict[str, QRadioButton] = {}
        options_by_value: dict[str, dict] = {}

        default_value = str(cfg.get("default", ""))
        extras_host = QWidget()
        extras_layout = QVBoxLayout(extras_host)
        extras_layout.setContentsMargins(20, 0, 0, 0)
        extras_layout.setSpacing(6)

        def clear_layout(layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                child_layout = item.layout()
                if widget is not None:
                    widget.deleteLater()
                elif child_layout is not None:
                    clear_layout(child_layout)

        def selected_value() -> str:
            for value, btn in buttons_by_value.items():
                if btn.isChecked():
                    return value
            return default_value

        def rebuild_extras() -> None:
            clear_layout(extras_layout)

            selected = selected_value()
            option_cfg = options_by_value.get(selected, {})
            extras = option_cfg.get("extras", []) or []

            for extra_cfg in extras:
                widget = self.build(extra_cfg)
                extras_layout.addWidget(widget)

            self.refresh_all()

        for i, option in enumerate(cfg.get("options", [])):
            option_label = str(option["label"])
            option_value = str(option["value"])

            btn = QRadioButton(option_label)
            button_group.addButton(btn, i)
            buttons_by_value[option_value] = btn
            options_by_value[option_value] = option

            if option_value == default_value:
                btn.setChecked(True)

            btn.toggled.connect(rebuild_extras)
            radio_row.addWidget(btn)

        if orientation == "horizontal":
            radio_row.addStretch()

        outer.addLayout(radio_row)
        outer.addWidget(extras_host)

        self._register_binding(
            cfg["key"],
            container,
            selected_value,
            cfg,
        )

        rebuild_extras()
        return container
    
    def _build_radio_with_shared_extras(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", ""))
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 22, 12, 12)
        layout.setSpacing(8)

        orientation = str(cfg.get("orientation", "vertical")).lower()
        radio_row = QHBoxLayout() if orientation == "horizontal" else QVBoxLayout()
        radio_row.setContentsMargins(0, 0, 0, 0)
        radio_row.setSpacing(10 if orientation == "horizontal" else 4)

        button_group = QButtonGroup(box)
        buttons_by_value: dict[str, QRadioButton] = {}

        default_value = str(cfg.get("default", ""))
        disable_value = str(cfg.get("disable_value", ""))

        for i, option in enumerate(cfg.get("options", [])):
            option_label = str(option["label"])
            option_value = str(option["value"])

            btn = QRadioButton(option_label)
            button_group.addButton(btn, i)
            buttons_by_value[option_value] = btn

            if option_value == default_value:
                btn.setChecked(True)

            radio_row.addWidget(btn)

        if orientation == "horizontal":
            radio_row.addStretch()

        layout.addLayout(radio_row)

        extras_host = QWidget()
        extras_layout = QVBoxLayout(extras_host)
        extras_layout.setContentsMargins(0, 0, 0, 0)
        extras_layout.setSpacing(6)

        shared_widgets: list[QWidget] = []
        for extra_cfg in cfg.get("shared_extras", []) or []:
            widget = self.build(extra_cfg)
            extras_layout.addWidget(widget)
            shared_widgets.append(widget)

        layout.addWidget(extras_host)

        def selected_value() -> str:
            for value, btn in buttons_by_value.items():
                if btn.isChecked():
                    return value
            return default_value

        def update_state() -> None:
            enabled = selected_value() != disable_value
            for widget in shared_widgets:
                widget.setEnabled(enabled)
            self.refresh_all()

        self._register_binding(
            cfg["key"],
            box,
            selected_value,
            cfg,
        )

        for btn in buttons_by_value.values():
            btn.toggled.connect(update_state)

        update_state()
        return box
    
    def _build_switch_with_extras(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        key = str(cfg["key"])
        default_mode = "b" if str(cfg.get("default", "a")).lower() == "b" else "a"

        toggle = ToggleSwitch()
        toggle.setChecked(default_mode == "b")
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        state_text_label = QLabel()
        layout.addWidget(state_text_label, 0, Qt.AlignmentFlag.AlignVCenter)

        control_a_cfg = dict(cfg.get("control_a") or {})
        control_b_cfg = dict(cfg.get("control_b") or {})
        if not control_a_cfg or not control_b_cfg:
            raise ValueError("switch_with_extras requires both 'control_a' and 'control_b'")

        combo_a = self._make_combo(
            options=control_a_cfg.get("options", []),
            default=control_a_cfg.get("default"),
            enabled=True,
            visible=True,
        )
        full_width = bool(cfg.get("full_width"))

        combo_a.setFixedHeight(24)
        if not full_width:
            combo_a.setFixedWidth(140)

        text_b = QLineEdit()
        text_b.setText(str(control_b_cfg.get("default", "")))
        text_b.setFixedHeight(24)
        if not full_width:
            text_b.setFixedWidth(140)

        placeholder = control_b_cfg.get("placeholder")
        if placeholder is not None:
            text_b.setPlaceholderText(str(placeholder))

        stack_host = QWidget()
        stack = QStackedLayout(stack_host)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        stack.addWidget(combo_a)
        stack.addWidget(text_b)

        if full_width:
            layout.addWidget(stack_host, 1, Qt.AlignmentFlag.AlignVCenter)
        else:
            stack_host.setFixedWidth(140)
            layout.addWidget(stack_host, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addStretch(1)

        base_field_name = str(cfg.get("field_name", "")).strip()
        fallback_a = str(cfg.get("state_name_a", "Option A"))
        fallback_b = str(cfg.get("state_name_b", "Option B"))

        def current_mode():
            return "b" if toggle.isChecked() else "a"

        def current_label_text() -> str:
            required_now = self.rules.cfg_is_currently_required(cfg)
            suffix = "*" if required_now else ""

            if base_field_name:
                if current_mode() == "b":
                    return f"Enter {base_field_name}{suffix}"
                return f"Select {base_field_name}{suffix}"

            if current_mode() == "b":
                return fallback_b + suffix
            return fallback_a + suffix

        def apply_state():
            use_text = current_mode() == "b"
            stack.setCurrentIndex(1 if use_text else 0)
            state_text_label.setText(current_label_text())
            combo_a.setEnabled(not use_text)
            text_b.setEnabled(use_text)
            self.refresh_all()

        def get_mode_value():
            return current_mode()

        self._register_binding(key, container, get_mode_value, cfg)

        mode_cfg = {
            "required": bool(cfg.get("required")),
            "_switch_parent_cfg": dict(cfg),
        }
        self._register_binding(f"{key}_mode", container, get_mode_value, mode_cfg)

        self._register_binding(
            str(control_a_cfg["key"]),
            combo_a,
            combo_a.currentData,
            control_a_cfg,
        )
        self._register_binding(
            str(control_b_cfg["key"]),
            text_b,
            lambda: text_b.text().strip(),
            control_b_cfg,
        )

        toggle.toggled.connect(apply_state)
        combo_a.currentIndexChanged.connect(self.refresh_all)
        text_b.textChanged.connect(self.refresh_all)

        container._switch_toggle = toggle
        container._switch_label = state_text_label
        container._switch_stack = stack
        container._switch_combo = combo_a
        container._switch_text = text_b
        container._switch_parent_cfg = dict(cfg)

        container._initial_mode = default_mode
        container._initial_column_value = combo_a.currentData()
        container._initial_text_value = text_b.text()

        apply_state()
        return container

    def _build_select(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        combo = self._make_combo(
            options=cfg.get("options", []),
            default=cfg.get("default"),
            enabled=True,
            visible=True,
        )
        layout.addWidget(combo)

        self._register_binding(cfg["key"], box, lambda: combo.currentData(), cfg)
        combo.currentIndexChanged.connect(self.refresh_all)
        return box

    def _build_compact_select(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            layout.addWidget(QLabel(label_text))

        combo = QComboBox()
        combo.setFixedHeight(24)

        for text, value in self._iter_options(cfg.get("options", [])):
            combo.addItem(str(text), value)

        default = cfg.get("default")
        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        if cfg.get("full_width"):
            layout.addWidget(combo)
        else:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            row.addWidget(combo)
            row.addStretch()
            layout.addLayout(row)

        def reset():
            if default is None:
                return
            idx = combo.findData(default)
            if idx < 0:
                return
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        self._register_binding(cfg["key"], container, combo.currentData, cfg, reset_to_default=reset)
        combo.currentIndexChanged.connect(self.refresh_all)

        depends_on = cfg.get("depends_on")
        options_provider = cfg.get("options_provider")
        if depends_on and callable(options_provider):
            _prev_parent: list = [object()]  # sentinel: guaranteed != any real value on first call

            def set_options(options: list) -> None:
                parent_value = self.ctx.get(depends_on)
                is_valid = parent_value is not None and parent_value != SENTINEL_SELECT
                parent_changed = parent_value != _prev_parent[0]
                _prev_parent[0] = parent_value

                current_value = combo.currentData()

                combo.blockSignals(True)
                combo.clear()
                for text, value in self._iter_options(options):
                    combo.addItem(str(text), value)

                if parent_changed or not is_valid:
                    reset = cfg.get("default")
                    idx = combo.findData(reset) if reset is not None else -1
                    combo.setCurrentIndex(idx if idx >= 0 else (0 if combo.count() else -1))
                else:
                    idx = combo.findData(current_value)
                    combo.setCurrentIndex(idx if idx >= 0 else (0 if combo.count() else -1))

                combo.setEnabled(is_valid)
                combo.blockSignals(False)
                self.refresh_all()

            combo.setEnabled(False)

            self.ctx.dynamic_multis.append(
                DynamicMultiBinding(
                    depends_on=depends_on,
                    set_options=set_options,
                    read_selected=combo.currentData,
                    options_provider=options_provider,
                )
            )

        return container

    def _build_range_select(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        options = cfg.get("options", [])
        start_key = cfg.get("start_key", f'{cfg["key"]}_start')
        end_key = cfg.get("end_key", f'{cfg["key"]}_end')

        start_combo = QComboBox()
        end_combo = QComboBox()

        for text, value in self._iter_options(options):
            start_combo.addItem(str(text), value)
            end_combo.addItem(str(text), value)

        start_default = cfg.get("default_start")
        if start_default is not None:
            idx = start_combo.findData(start_default)
            if idx >= 0:
                start_combo.setCurrentIndex(idx)

        end_default = cfg.get("default_end")
        if end_default is not None:
            idx = end_combo.findData(end_default)
            if idx >= 0:
                end_combo.setCurrentIndex(idx)

        start_col = QVBoxLayout()
        start_col.setContentsMargins(0, 0, 0, 0)
        start_col.setSpacing(2)
        start_col.addWidget(QLabel(cfg.get("start_label", "Address start")))
        start_col.addWidget(start_combo)

        end_col = QVBoxLayout()
        end_col.setContentsMargins(0, 0, 0, 0)
        end_col.setSpacing(2)
        end_col.addWidget(QLabel(cfg.get("end_label", "Address end")))
        end_col.addWidget(end_combo)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addLayout(start_col)
        row.addWidget(QLabel("-"))
        row.addLayout(end_col)
        row.addStretch()

        layout.addLayout(row)

        self._register_binding(
            start_key,
            container,
            start_combo.currentData,
            {"required": start_key in cfg.get("required_keys", [])},
        )
        self._register_binding(
            end_key,
            container,
            end_combo.currentData,
            {"required": end_key in cfg.get("required_keys", [])},
        )

        start_combo.currentIndexChanged.connect(self.refresh_all)
        end_combo.currentIndexChanged.connect(self.refresh_all)

        return container

    def _build_toggle_select(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        default_state = (cfg.get("default") or "off").strip().lower()
        rb_off = self._make_radio(cfg["toggle"]["off"], "off", checked=(default_state == "off"))
        rb_on = self._make_radio(cfg["toggle"]["on"], "on", checked=(default_state == "on"))

        layout.addWidget(rb_off)

        row = QHBoxLayout()
        row.addWidget(rb_on)

        options = cfg.get("options") or []
        combo = self._make_combo(options=options, default=None, enabled=False, visible=bool(options))
        if combo.isVisible():
            row.addWidget(combo)

        layout.addLayout(row)

        extras = self._build_extras_controller(
            base_layout=layout,
            extras_cfg=cfg.get("extra", {}) or {},
            is_enabled_fn=rb_on.isChecked,
            get_value_fn=combo.currentData,
        )

        def update_state():
            combo.setEnabled(rb_on.isChecked() and combo.isVisible())
            extras.refresh()
            self.refresh_all()

        rb_on.toggled.connect(update_state)
        combo.currentIndexChanged.connect(update_state)
        update_state()

        def read():
            if not rb_on.isChecked():
                return {"enabled": False}
            result = {"enabled": True, "value": combo.currentData()}
            extras.read_into(result)
            return result

        self._register_binding(cfg["key"], box, read, cfg)
        return box

    def _build_multi_select(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 22, 12, 12)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.viewport().setStyleSheet("border: none;")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)

        key = cfg["key"]
        mutex_group = cfg.get("mutex_group")
        rows: dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]] = {}
        self.ctx.multi_rows[key] = rows

        def read_selected() -> list:
            return [value for value, (cb, _x, _stack) in rows.items() if cb.isChecked()]

        def notify_mutex_changed():
            if mutex_group and self.mutex is not None:
                self.mutex.refresh_group(mutex_group)
            self.rules.refresh_required_state()

        def set_options(options: list[tuple[str, Any]]):
            prev_selected = set(read_selected())

            while inner_layout.count():
                item = inner_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            rows.clear()

            probe = QCheckBox()
            iw = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, None, probe)
            ih = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight, None, probe)
            row_h = ih

            for label, value in options:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                cb = QCheckBox()
                cb.setChecked(value in prev_selected)
                cb.setFixedSize(iw, ih)

                x = QLabel("X")
                x.setAlignment(Qt.AlignmentFlag.AlignCenter)
                x.setFixedSize(iw, ih)
                x.setFrameShape(QFrame.Shape.Box)
                x.setLineWidth(1)

                indicator = QWidget()
                stack = QStackedLayout(indicator)
                stack.setContentsMargins(0, 0, 0, 0)
                stack.addWidget(cb)
                stack.addWidget(x)
                stack.setCurrentWidget(cb)

                txt = QLabel(str(label))
                txt.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

                row_layout.addWidget(indicator, 0, Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(txt, 1, Qt.AlignmentFlag.AlignVCenter)

                cb.stateChanged.connect(notify_mutex_changed)

                rows[value] = (cb, x, stack)
                inner_layout.addWidget(row)

                row_h = max(row_h, txt.sizeHint().height(), ih)
                row.setFixedHeight(row_h)

            inner_layout.addStretch(1)

            if rows:
                viewport_h = (row_h * 2) + inner_layout.spacing()
                scroll.setFixedHeight(viewport_h + 6)

                sb = scroll.verticalScrollBar()
                step = max(1, row_h * 2)
                sb.setSingleStep(step)
                sb.setPageStep(step)

            inner_layout.activate()
            inner.adjustSize()
            scroll.updateGeometry()
            box.updateGeometry()

            if mutex_group and self.mutex is not None:
                self.mutex.refresh_group(mutex_group)

        set_options(cfg.get("options", []) or [])

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        def reset():
            for (cb, _x, _stack) in rows.values():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)

        self._register_binding(key, box, read_selected, cfg, reset_to_default=reset)

        depends_on = cfg.get("depends_on")
        options_provider = cfg.get("options_provider")
        if depends_on and callable(options_provider):
            self.ctx.dynamic_multis.append(
                DynamicMultiBinding(
                    depends_on=depends_on,
                    set_options=set_options,
                    read_selected=read_selected,
                    options_provider=options_provider,
                )
            )

        if mutex_group:
            self.ctx.mutex_groups.setdefault(str(mutex_group), []).append(key)

        return box

    def _build_number(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", ""))
        layout = QVBoxLayout(box)

        default_value = int(cfg.get("default", 0))

        spin = QSpinBox()
        spin.setMinimum(int(cfg.get("min", 0)))
        spin.setMaximum(int(cfg.get("max", 10_000_000)))
        spin.setValue(default_value)
        layout.addWidget(spin)

        key = cfg["key"]
        self.ctx.number_widgets[key] = spin

        def reset():
            spin.blockSignals(True)
            spin.setValue(default_value)
            spin.blockSignals(False)

        self._register_binding(key, box, spin.value, cfg, reset_to_default=reset)

        spin.valueChanged.connect(self.refresh_all)

        if key in ("items_file1", "items_file2"):
            spin.valueChanged.connect(lambda _v, k=key: self.sync_item_split_numbers(k))

        return box

    def _build_table_preview(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", "Preview"))
        layout = QVBoxLayout(box)

        rows = cfg.get("rows", []) or []
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAlternatingRowColors(True)

        if rows:
            columns = list(rows[0].keys())
            table.setColumnCount(len(columns))
            table.setRowCount(len(rows))
            table.setHorizontalHeaderLabels([str(c) for c in columns])

            for r, row in enumerate(rows):
                for c, col in enumerate(columns):
                    value = row.get(col, "")
                    item = QTableWidgetItem("" if value is None else str(value))
                    table.setItem(r, c, item)

            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
            table.verticalHeader().setVisible(False)
        else:
            table.setColumnCount(0)
            table.setRowCount(0)

        visible_rows = min(max(len(rows), 1), 10)
        row_height = table.verticalHeader().defaultSectionSize() if table.rowCount() else 30
        header_height = table.horizontalHeader().height()
        frame_height = 8
        table.setMinimumHeight((visible_rows * row_height) + header_height + frame_height)
        table.setMaximumHeight((visible_rows * row_height) + header_height + frame_height + 4)

        layout.addWidget(table)
        return box

    def _build_section(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", "Section"))
        layout = QVBoxLayout(box)

        for child in cfg.get("children", []):
            layout.addWidget(self.build(child))

        return box

    def _build_compact_select_row(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for child in cfg.get("children", []):
            layout.addWidget(self.build(child), 1)

        return container

    def _build_labeled_select_row(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(str(cfg.get("label", "")))
        label.setMinimumWidth(int(cfg.get("label_width", 80)))
        layout.addWidget(label)

        combo = self._make_combo(
            options=cfg.get("options", []),
            default=cfg.get("default"),
            enabled=True,
            visible=True,
        )
        layout.addWidget(combo, 1)

        self._register_binding(cfg["key"], container, lambda: combo.currentData(), cfg)
        combo.currentIndexChanged.connect(self.refresh_all)
        return container

    def _build_checkbox(self, cfg: dict) -> QWidget:
        cb = QCheckBox(str(cfg.get("label", "")))
        cb.setChecked(bool(cfg.get("default", False)))

        key = str(cfg["key"])
        self._register_binding(key, cb, cb.isChecked, cfg)
        cb.toggled.connect(lambda _checked: self.refresh_all())
        return cb

    def _iter_options(self, options: Optional[Iterable]) -> Iterable[Tuple[str, Any]]:
        for opt in options or []:
            if isinstance(opt, dict):
                yield str(opt.get("label", "")), opt.get("value")
            elif isinstance(opt, (list, tuple)) and len(opt) == 2:
                label, value = opt
                yield str(label), value
            else:
                yield str(opt), opt

    def _get_checked_value(self, radios: list[QRadioButton], default=None):
        return next((r._value for r in radios if r.isChecked()), default)

    def _make_combo(self,*,options,default=None,enabled: bool = True,
                    visible: bool = True) -> QComboBox:
        combo = QComboBox()
        for label, value in self._iter_options(options):
            combo.addItem(label, value)

        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        combo.setEnabled(bool(enabled))
        combo.setVisible(bool(visible))
        return combo

    def _make_radio(self, label: str, value: Any, checked: bool = False) -> QRadioButton:
        rb = QRadioButton(label)
        rb._value = value
        rb.setChecked(bool(checked))
        return rb

    def _make_radio_group(self,*,parent_layout,options,default=None,orientation: str = "horizontal") -> tuple[list[QRadioButton], Callable[[], Any]]:
        radios: list[QRadioButton] = []

        if orientation == "vertical":
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                parent_layout.addWidget(rb)
                radios.append(rb)
        else:
            row = QHBoxLayout()
            parent_layout.addLayout(row)
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                row.addWidget(rb)
                radios.append(rb)
            row.addStretch()

        return radios, (lambda: self._get_checked_value(radios, default=default))

    def _register_binding(self,key: str,widget: QWidget,get_value: Callable[[], Any],cfg: dict,reset_to_default: Callable[[], None] | None = None,) -> None:
        if not key:
            return
        binding = ControlBinding(key=str(key),widget=widget,get_value=get_value,cfg=cfg,required=bool(cfg.get("required")),reset_to_default=reset_to_default,)
        self.ctx.register(binding)