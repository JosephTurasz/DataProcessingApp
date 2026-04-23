from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtWidgets import QWidget,QComboBox,QLineEdit,QLabel,QToolButton

@dataclass
class ControlBinding:
    key: str
    widget: QWidget
    get_value: Callable[[], Any]
    cfg: dict = field(default_factory=dict)
    required: bool = False
    reset_to_default: Callable[[], None] | None = None

@dataclass
class DynamicMultiBinding:
    depends_on: str
    set_options: Callable[[list[tuple[str, Any]]], None]
    read_selected: Callable[[], list]
    options_provider: Callable[[Any], list]

@dataclass
class PagerState:
    group: str
    items: list[dict]
    page: int = 0
    page_size: int = 2
    label: QLabel | None = None
    btn_up: QToolButton | None = None
    btn_down: QToolButton | None = None
    nav_widget: QWidget | None = None

class ExtrasBinding:
    def __init__(self,widgets_by_option: dict[Any, list[tuple[str, QWidget]]],enabled_when: Callable[[], bool],selected_value: Callable[[], Any]):
        self.widgets_by_option = widgets_by_option
        self.enabled_when = enabled_when
        self.selected_value = selected_value

    def refresh(self) -> None:
        enabled = bool(self.enabled_when())
        current = self.selected_value()

        for option, widgets in self.widgets_by_option.items():
            active = enabled and (option == "__enabled__" or option == current)
            for _, widget in widgets:
                widget.setEnabled(active)

    def read_into(self, result: dict) -> None:
        current = self.selected_value()
        widgets = list(self.widgets_by_option.get(current, []))
        widgets += self.widgets_by_option.get("__enabled__", [])

        for key, widget in widgets:
            if isinstance(widget, QLineEdit):
                result[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentData()
