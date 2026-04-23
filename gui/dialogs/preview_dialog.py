from PySide6.QtWidgets import QVBoxLayout, QPushButton, QDialog, QMenu, QInputDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from gui.pandas_model import DragDropPandasModel
from gui.tables.table import DragDropTableView

from config.constants import PREVIEW_HEIGHT, PREVIEW_WIDTH

class PreviewDialog(QDialog):
    def __init__(self, dataframe, parent=None, title="Preview"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.model = DragDropPandasModel(dataframe)
        layout = QVBoxLayout(self)
        self.table_view = DragDropTableView()
        self.table_view.setModel(self.model)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table_view)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        self.table_view.verticalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    def get_dataframe(self):
        return self.model.get_dataframe()

    def keyPressEvent(self, event: QKeyEvent):
        model = self.table_view.model()
        sel = self.table_view.selectedIndexes()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and event.key() == Qt.Key.Key_C:
            model.copy_selection(sel)
            return
        if ctrl and event.key() == Qt.Key.Key_V:
            start_index = sel[0] if sel else model.index(0, 0)
            model.paste_at(start_index)
            return
        if ctrl and event.key() == Qt.Key.Key_Z:
            model.undo()
            return
        if (ctrl and event.key() == Qt.Key.Key_Y) or (
            ctrl and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Z):
            model.redo()
            return
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if sel:
                model.clear_selection(sel)
            return
        super().keyPressEvent(event)
        
    def show_header_context_menu(self, pos):
        model = self.table_view.model()
        menu = QMenu(self)
        sender = self.sender()
        # ---------- COLUMN HEADER ----------
        if sender == self.table_view.horizontalHeader():
            col = sender.logicalIndexAt(pos)
            if col < 0:
                return
            menu.addAction("Insert Left", lambda: model.insert_column_left(col))
            menu.addAction("Insert Multiple Left", lambda: self.insert_columns_dialog(col, left=True))
            menu.addSeparator()
            menu.addAction("Insert Right", lambda: model.insert_column_right(col))
            menu.addAction("Insert Multiple Right", lambda: self.insert_columns_dialog(col, left=False))
            menu.addSeparator()
            menu.addAction("Rename", lambda: self.table_view.start_header_rename(col))
            menu.addSeparator()
            menu.addAction("Delete", lambda: self.delete_columns_from_selection_or_clicked(col))
            menu.exec(sender.mapToGlobal(pos))
            return
        # ---------- ROW HEADER ----------
        if sender == self.table_view.verticalHeader():
            row = sender.logicalIndexAt(pos)
            if row < 0:
                return
            menu.addAction("Insert Above", lambda: model.insert_row_above(row))
            menu.addAction("Insert Multiple Above", lambda: self.insert_rows_dialog(row, above=True))
            menu.addSeparator()
            menu.addAction("Insert Below", lambda: model.insert_row_below(row))
            menu.addAction("Insert Multiple Below", lambda: self.insert_rows_dialog(row, above=False))
            menu.addSeparator()
            menu.addAction("Delete", lambda: self.delete_rows_from_selection_or_clicked(row))
            menu.exec(sender.mapToGlobal(pos))
            return

    def show_context_menu(self, pos):
        view = self.table_view
        model = view.model()
        indexes = view.selectedIndexes()
        menu = QMenu(self)
        menu.addAction("Copy", lambda: model.copy_selection(indexes))
        menu.addAction(
            "Paste",
            lambda: model.paste_at(indexes[0] if indexes else model.index(0, 0)))
        menu.addSeparator()
        menu.addAction("Undo", model.undo)
        menu.addAction("Redo", model.redo)
        menu.addSeparator()
        menu.addAction(
            "Clear",
            lambda: model.clear_selection(indexes))
        menu.exec(view.viewport().mapToGlobal(pos))
        
    def insert_rows_dialog(self, row: int, above: bool):
        model = self.table_view.model()
        n, ok = QInputDialog.getInt(self, "Insert rows", "How many rows?", 1, 1, 10000, 1)
        if not ok:
            return
        if above:
            model.insert_rows_above(row, n)
        else:
            model.insert_rows_below(row, n)

    def insert_columns_dialog(self, col: int, left: bool):
        model = self.table_view.model()
        n, ok = QInputDialog.getInt(self, "Insert columns", "How many columns?", 1, 1, 10000, 1)
        if not ok:
            return
        if left:
            model.insert_columns_left(col, n)
        else:
            model.insert_columns_right(col, n)
            
    def _selected_row_header_indexes(self):
        sm = self.table_view.selectionModel()
        if not sm:
            return []
        return sorted({idx.row() for idx in sm.selectedRows()})

    def _selected_col_header_indexes(self):
        sm = self.table_view.selectionModel()
        if not sm:
            return []
        return sorted({idx.column() for idx in sm.selectedColumns()})
    
    def delete_rows_from_selection_or_clicked(self, clicked_row: int):
        model = self.table_view.model()
        rows = self._selected_row_header_indexes()
        if not rows:
            rows = [clicked_row]
        model.delete_rows(rows)

    def delete_columns_from_selection_or_clicked(self, clicked_col: int):
        model = self.table_view.model()
        cols = self._selected_col_header_indexes()
        if not cols:
            cols = [clicked_col]
        model.delete_columns(cols)