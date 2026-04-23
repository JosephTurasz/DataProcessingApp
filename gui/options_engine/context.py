from __future__ import annotations

from typing import Any

from gui.options_engine.bindings import ControlBinding, DynamicMultiBinding

from PySide6.QtWidgets import (QWidget,QLabel,QCheckBox,QStackedLayout,QSpinBox)

class DialogContext:
    def __init__(self):
        self.bindings: dict[str, ControlBinding] = {}
        self.dynamic_multis: list[DynamicMultiBinding] = []
        self.multi_rows: dict[str, dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]]] = {}
        self.mutex_groups: dict[str, list[str]] = {}
        self.number_widgets: dict[str, QSpinBox] = {}
        self.required_keys: set[str] = set()

    def register(self, binding: ControlBinding) -> None:
        if binding.key:
            self.bindings[binding.key] = binding
            if binding.required:
                self.required_keys.add(binding.key)

    def get(self, key: str) -> Any:
        binding = self.bindings.get(str(key))
        if not binding:
            return None
        return binding.get_value()

    def widget_for(self, key: str) -> QWidget | None:
        binding = self.bindings.get(str(key))
        return binding.widget if binding else None
    
    def binding(self, key: str):
        return self.bindings.get(key)