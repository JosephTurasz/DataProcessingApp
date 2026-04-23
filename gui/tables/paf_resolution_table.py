from __future__ import annotations

import pandas as pd

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView

from gui.pandas_model import DragDropPandasModel
from gui.tables.table import DragDropTableView

class PAFResolutionTable(DragDropTableView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)

        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)

        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self._copy_shortcut.activated.connect(self._copy_selection)

        self._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self._paste_shortcut.activated.connect(self._paste_selection)

    def set_preview_dataframe(self, df: pd.DataFrame):
        model = DragDropPandasModel(df.copy())
        self.setModel(model)

        try:
            self.resizeColumnsToContents()
            self.resizeRowsToContents()
        except Exception:
            pass

    def dataframe(self) -> pd.DataFrame:
        model = self.model()
        if model is None:
            return pd.DataFrame()
        return model.get_dataframe()

    def _copy_selection(self):
        model = self.model()
        if model is None:
            return
        model.copy_selection(self.selectedIndexes())

    def _paste_selection(self):
        model = self.model()
        if model is None:
            return
        model.paste_at(self.currentIndex())

    def keyPressEvent(self, event):
        model = self.model()
        if model is not None and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            model.clear_selection(self.selectedIndexes())
            event.accept()
            return
        super().keyPressEvent(event)

    def startDrag(self, supportedActions):
        if len(self.selectedIndexes()) != 1:
            return
        super().startDrag(supportedActions)