from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView

from gui.tables.resolution_table_base import ResolutionTableBase


class ServiceResolutionTable(ResolutionTableBase):
    HEADERS = ["Length", "Width", "Height", "Weight", "Service", "Reject Reason"]
    EDITABLE_COLUMNS = {"Length", "Width", "Height", "Weight", "Service"}
    SELECTION_BEHAVIOR = QAbstractItemView.SelectionBehavior.SelectItems
