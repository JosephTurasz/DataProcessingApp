import re
import json
import secrets
import pandas as pd

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QAbstractTableModel, QMimeData, QModelIndex, QByteArray

from config.constants import PREVIEW_UNDO_LIMIT

_DUP_RE = re.compile(r"^(.*?)(?: \((\d+)\))?$")

class DragDropPandasModel(QAbstractTableModel):
    MIME_TYPE = "application/x-pandas-cell-block"

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        self.undo_stack = []
        self.redo_stack = []
        self._drag_token = secrets.token_hex(16)

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return str(self.df.iat[index.row(), index.column()])
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            self.push_undo_state()
            self.df.iat[index.row(), index.column()] = value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsEditable)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self.df.columns[section])
        return str(section + 1)

    def _next_unique_name(self, desired: str, col_being_renamed: int) -> str:
        desired = str(desired).strip()
        if not desired:
            desired = "Column"

        existing = [str(c) for i, c in enumerate(self.df.columns) if i != col_being_renamed]
        existing_set = set(existing)

        if desired not in existing_set:
            return desired
        m = _DUP_RE.match(desired)
        base = (m.group(1) or "").strip() or desired
        n = 1
        while True:
            candidate = f"{base} ({n})"
            if candidate not in existing_set and candidate != desired:
                return candidate
            n += 1

    def rename_column(self, col: int, new_name: str):
        new_name = (new_name or "").strip()
        if not new_name:
            return

        current = str(self.df.columns[col])
        final_name = self._next_unique_name(new_name, col)

        if current == final_name:
            return

        self.push_undo_state()
        cols = [str(c) for c in self.df.columns]
        cols[col] = final_name
        self.df.columns = cols
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, col, col)

    def insert_row_above(self, row: int):
        self.push_undo_state()
        self.beginInsertRows(QModelIndex(), row, row)
        empty = pd.DataFrame([[""] * self.columnCount()], columns=self.df.columns)
        top = self.df.iloc[:row]
        bottom = self.df.iloc[row:]
        self.df = pd.concat([top, empty, bottom], ignore_index=True)
        self.endInsertRows()

    def insert_row_below(self, row: int):
        self.insert_row_above(row + 1)

    def insert_rows_above(self, row: int, count: int = 1):
        count = int(count)
        if count <= 0:
            return
        self.push_undo_state()
        empty = pd.DataFrame([[""] * self.columnCount()] * count, columns=self.df.columns)
        self.df = pd.concat([self.df.iloc[:row], empty, self.df.iloc[row:]], ignore_index=True)
        self.layoutChanged.emit()

    def insert_rows_below(self, row: int, count: int = 1):
        self.insert_rows_above(row + 1, count)

    def insert_column_left(self, col: int):
        self.push_undo_state()
        self.beginInsertColumns(QModelIndex(), col, col)
        name = f"Column{self.columnCount() + 1}"
        self.df.insert(col, name, "")
        self.endInsertColumns()

    def insert_column_right(self, col: int):
        self.insert_column_left(col + 1)

    def insert_columns_left(self, col: int, count: int = 1):
        count = int(count)
        if count <= 0:
            return
        self.push_undo_state()
        for i in range(count):
            name = f"Column{self.columnCount() + 1}"
            self.df.insert(col + i, name, "")
        self.layoutChanged.emit()

    def insert_columns_right(self, col: int, count: int = 1):
        self.insert_columns_left(col + 1, count)

    def delete_rows(self, rows):
        rows = sorted({int(r) for r in rows})
        if not rows:
            return
        if self.rowCount() <= 1:
            return
        if len(rows) >= self.rowCount():
            rows = rows[:-1]
        self.push_undo_state()
        self.beginResetModel()
        self.df = self.df.drop(index=rows).reset_index(drop=True)
        self.endResetModel()

    def delete_columns(self, cols):
        cols = sorted({int(c) for c in cols})
        if not cols:
            return
        if self.columnCount() <= 1:
            return
        if len(cols) >= self.columnCount():
            cols = cols[:-1]
        self.push_undo_state()
        self.beginResetModel()
        drop_labels = [self.df.columns[c] for c in cols if 0 <= c < self.columnCount()]
        self.df = self.df.drop(columns=drop_labels)
        self.endResetModel()
    # ---------------- Drag/drop ----------------
    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, indexes):
        mime = QMimeData()
        if not indexes:
            return mime

        rows = sorted({idx.row() for idx in indexes if idx.isValid()})
        cols = sorted({idx.column() for idx in indexes if idx.isValid()})
        if not rows or not cols:
            return mime

        payload = {"v": 1,"token": self._drag_token,"r0": rows[0],"r1": rows[-1],"c0": cols[0],"c1": cols[-1],}
        mime.setData(self.MIME_TYPE, QByteArray(json.dumps(payload).encode("utf-8")))
        return mime

    def dropMimeData(self, mime, action, dest_row, dest_col, parent):
        if action != Qt.DropAction.MoveAction or not mime.hasFormat(self.MIME_TYPE):
            return False

        if parent is not None and parent.isValid():
            dest_row = parent.row()
            dest_col = parent.column()

        if dest_row is None or dest_col is None or dest_row < 0 or dest_col < 0:
            return False

        try:
            payload = json.loads(bytes(mime.data(self.MIME_TYPE)).decode("utf-8"))
        except Exception:
            return False

        if payload.get("v") != 1 or payload.get("token") != self._drag_token:
            return False

        try:
            r0 = int(payload.get("r0", -1))
            r1 = int(payload.get("r1", -1))
            c0 = int(payload.get("c0", -1))
            c1 = int(payload.get("c1", -1))
        except Exception:
            return False

        if r0 < 0 or c0 < 0 or r1 < r0 or c1 < c0:
            return False

        height = (r1 - r0) + 1
        width = (c1 - c0) + 1

        max_row = max(0, self.rowCount() - height)
        max_col = max(0, self.columnCount() - width)
        dest_row = max(0, min(int(dest_row), max_row))
        dest_col = max(0, min(int(dest_col), max_col))

        self.beginResetModel()
        try:
            orig = self.df.copy()
            move_pairs = []
            for dr in range(height):
                for dc in range(width):
                    sr = r0 + dr
                    sc = c0 + dc
                    tr = dest_row + dr
                    tc = dest_col + dc
                    if 0 <= sr < self.rowCount() and 0 <= sc < self.columnCount():
                        if 0 <= tr < self.rowCount() and 0 <= tc < self.columnCount():
                            move_pairs.append(((sr, sc), (tr, tc)))

            if not move_pairs:
                return False

            self.push_undo_state()
            
            for (sr, sc), (tr, tc) in move_pairs:
                self.df.iat[tr, tc] = orig.iat[sr, sc]

            dest_set = {dst for (_, dst) in move_pairs}
            src_set = {src for (src, _) in move_pairs}
            for (sr, sc) in src_set:
                if (sr, sc) not in dest_set:
                    self.df.iat[sr, sc] = ""

            return True
        finally:
            self.endResetModel()

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction
    
    def get_dataframe(self):
        return self.df.copy()
    # ---------------- Undo/redo ----------------
    def push_undo_state(self):
        self.undo_stack.append(self.df.copy())
        if len(self.undo_stack) > PREVIEW_UNDO_LIMIT:
            del self.undo_stack[:len(self.undo_stack) - PREVIEW_UNDO_LIMIT]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.df.copy())
            self.df = self.undo_stack.pop()
            self.layoutChanged.emit()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.df.copy())
            self.df = self.redo_stack.pop()
            self.layoutChanged.emit()
    # ---------------- Clipboard ops ----------------
    def copy_selection(self, indexes):
        if not indexes:
            return
        rows = sorted(set(i.row() for i in indexes))
        cols = sorted(set(i.column() for i in indexes))
        lines = []
        for r in rows:
            values = []
            for c in cols:
                val = str(self.df.iat[r, c]).replace("\n", " ").strip()
                values.append(val)
            lines.append("\t".join(values))
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)

    def paste_at(self, start_index):
        if not start_index.isValid():
            return
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        self.push_undo_state()
        rows = [r for r in text.split("\n") if r.strip() != ""]
        for r_i, row in enumerate(rows):
            cols = row.split("\t")
            for c_i, val in enumerate(cols):
                tr = start_index.row() + r_i
                tc = start_index.column() + c_i
                if tr < len(self.df) and tc < len(self.df.columns):
                    self.df.iat[tr, tc] = val
        self.layoutChanged.emit()

    def clear_selection(self, indexes):
        if not indexes:
            return
        self.push_undo_state()
        for idx in indexes:
            if idx.isValid():
                self.df.iat[idx.row(), idx.column()] = ""
        self.layoutChanged.emit()