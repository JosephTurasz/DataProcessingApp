from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from gui.options_engine.bindings import PagerState

class PagerManager:
    def __init__(self, rule_matches: Callable[[object], bool], widget_for: Callable[[str], QWidget | None],):
        self._rule_matches = rule_matches
        self._widget_for = widget_for
        self.states: dict[str, PagerState] = {}
        self.active_group: str | None = None

    def register_schema(self, schema: list[dict]) -> None:
        groups: dict[str, list[dict]] = {}

        for cfg in schema:
            group = cfg.get("page_group")
            if not group or not cfg.get("key"):
                continue
            group = str(group)
            groups.setdefault(group, []).append(cfg)

        def sort_key(c: dict) -> int:
            key = str(c.get("key", ""))
            digits = "".join(ch for ch in key if ch.isdigit())
            return int(digits) if digits else 999

        for group, items in groups.items():
            self.states[group] = PagerState(
                group=group,
                items=sorted(items, key=sort_key))

        if self.states and self.active_group is None:
            self.active_group = next(iter(self.states.keys()))

    def build_nav_row(self, group: str) -> QWidget:
        state = self.states[group]

        container = QWidget()
        nav_row = QHBoxLayout(container)
        nav_row.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("Navigate files:")
        btn_up = QToolButton()
        btn_up.setText("▲")
        btn_down = QToolButton()
        btn_down.setText("▼")
        lbl_status = QLabel("")

        nav_row.addWidget(lbl_title)
        nav_row.addWidget(btn_up)
        nav_row.addWidget(btn_down)
        nav_row.addWidget(lbl_status)
        nav_row.addStretch()

        state.label = lbl_status
        state.btn_up = btn_up
        state.btn_down = btn_down
        state.nav_widget = container

        btn_up.clicked.connect(lambda _=False, g=group: self.move(g, -1))
        btn_down.clicked.connect(lambda _=False, g=group: self.move(g, +1))

        return container

    def move(self, group: str, delta: int) -> None:
        state = self.states.get(group)
        if not state:
            return
        state.page = max(0, state.page + int(delta))
        self.refresh()

    def eligible_keys(self, items: list[dict]) -> list[str]:
        keys: list[str] = []

        for cfg in items:
            key = cfg.get("key")
            if not key:
                continue

            visible_if = cfg.get("visible_if")
            if visible_if and not self._rule_matches(visible_if):
                continue

            keys.append(str(key))

        return keys

    def refresh(self) -> None:
        for group, state in self.states.items():
            eligible = self.eligible_keys(state.items)
            page_size = int(state.page_size)
            page = int(state.page)

            if not eligible:
                if state.nav_widget:
                    state.nav_widget.setVisible(False)
                for cfg in state.items:
                    key = cfg.get("key")
                    if not key:
                        continue
                    widget = self._widget_for(str(key))
                    if widget:
                        widget.setVisible(False)
                continue

            if state.nav_widget:
                state.nav_widget.setVisible(True)

            max_page = (len(eligible) - 1) // page_size
            if page > max_page:
                page = max_page
                state.page = page

            start = page * page_size
            window = eligible[start : start + page_size]
            window_set = set(window)

            for cfg in state.items:
                key = str(cfg.get("key", ""))
                if not key:
                    continue

                widget = self._widget_for(key)
                if widget is None:
                    continue

                visible_if = cfg.get("visible_if")
                is_visible = True if not visible_if else bool(self._rule_matches(visible_if))
                widget.setVisible(is_visible and key in window_set)

            start_n = start + 1
            end_n = min(start + page_size, len(eligible))

            if state.label:
                state.label.setText(f"Showing {start_n}-{end_n} of {len(eligible)}")
            if state.btn_up:
                state.btn_up.setEnabled(page > 0)
            if state.btn_down:
                state.btn_down.setEnabled(page < max_page)