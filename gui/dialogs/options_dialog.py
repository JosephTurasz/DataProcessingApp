from __future__ import annotations

from gui.options_engine.context import DialogContext
from gui.options_engine.paging import PagerManager
from gui.options_engine.rules import DialogRules
from gui.options_engine.mutex import DialogMutexController
from gui.options_engine.building import DialogBuilder
from gui.options_engine.state_rules import StateRules

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QScrollArea,QFrame)

class OptionsDialog(QDialog):
    def __init__(self,schema: list[dict],parent=None,title: str = "Options",
        *,initial_size: tuple[int, int] = (600, 720),minimum_size: tuple[int, int] = (500, 650),minimum_content_width: int = 500,):
        super().__init__(parent)

        self.schema = schema
        self.ctx = DialogContext()
        self._ok_button = None

        self.setWindowTitle(title)
        self.resize(*initial_size)
        self.setMinimumSize(*minimum_size)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.rules = DialogRules(ctx=self.ctx,schema=self.schema,ok_button_getter=lambda: self._ok_button,)

        self.factory = DialogBuilder(ctx=self.ctx,rules=self.rules,mutex=None,
                                     refresh_all=self.refresh_all,sync_item_split_numbers=self.rules.sync_item_split_numbers,)

        self.mutex = DialogMutexController(ctx=self.ctx,iter_options=self.factory._iter_options,)
        self.factory.mutex = self.mutex

        self.pagers = PagerManager(rule_matches=self.rules.rule_matches,widget_for=self.ctx.widget_for)

        self.state_rules = StateRules(self.ctx,self.rules,self.mutex,self._set_bound_widget_enabled,pagers=self.pagers)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)

        self.scroll.setWidget(self.body)
        self.main_layout.addWidget(self.scroll, 1)

        self._initializing = True

        self._build_ui()
        self.body_layout.addStretch(1)
        self._add_dialog_buttons()
        self._initializing = False
        self.refresh_all()

        self.adjustSize()
        self.setMinimumWidth(max(self.minimumWidth(), minimum_content_width))

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_bound_widget_enabled(self, key: str, enabled: bool) -> None:
        binding = self.ctx.binding(str(key))
        if binding is None or binding.widget is None:
            return
        binding.widget.setEnabled(bool(enabled))

    def _build_ui(self) -> None:
        self.pagers.register_schema(self.schema)

        inserted_pager_groups: set[str] = set()
        active_group: str | None = None

        for cfg in self.schema:
            group = cfg.get("page_group")
            group = str(group) if group else None

            if active_group and group != active_group:
                if active_group not in inserted_pager_groups:
                    self.body_layout.addWidget(self.pagers.build_nav_row(active_group))
                    inserted_pager_groups.add(active_group)
                active_group = None

            if group:
                active_group = group

            widget = self.factory.build(cfg)
            self.body_layout.addWidget(widget)

            key = cfg.get("key")
            if key == "items_file1":
                self.rules.set_item_split_total(cfg.get("default"))

        if active_group and active_group not in inserted_pager_groups:
            self.body_layout.addLayout(self.pagers.build_nav_row(active_group))

    def _add_dialog_buttons(self) -> None:
        row = QHBoxLayout()
        row.addStretch()

        btn_cancel = QPushButton("Cancel")
        self._ok_button = QPushButton("Continue")
        self._ok_button.setDefault(True)

        btn_cancel.clicked.connect(self.reject)
        self._ok_button.clicked.connect(self.accept)

        row.addWidget(btn_cancel)
        row.addWidget(self._ok_button)
        self.main_layout.addLayout(row)

        self.rules.refresh_required_state()

    def _refresh_dynamic_multis(self) -> None:
        for binding in self.ctx.dynamic_multis:
            current_value = self.ctx.get(binding.depends_on)
            new_options = binding.options_provider(current_value)
            binding.set_options(new_options)

    def refresh_all(self) -> None:
        if getattr(self, "_initializing", False):
            return

        if getattr(self, "_refreshing", False):
            return

        self._refreshing = True
        try:
            self._refresh_dynamic_multis()
            self.rules.refresh_visibility()
            self.state_rules.apply_state()
            self.mutex.refresh_selects()

            for group in self.ctx.mutex_groups:
                self.mutex.refresh_group(group)

            for cfg in self.schema:
                self.rules.refresh_switch_labels(cfg)

            self.pagers.refresh()
            self.rules.refresh_required_state()
        finally:
            self._refreshing = False

    def keyPressEvent(self, event: QKeyEvent):
        if self.pagers.active_group and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.pagers.move(self.pagers.active_group,-1 if event.key() == Qt.Key.Key_Up else 1)
            return
        super().keyPressEvent(event)

    def get_results(self) -> dict:
        out = {}
        for key, binding in self.ctx.bindings.items():
            try:
                out[key] = binding.get_value()
            except RuntimeError:
                continue
        return out