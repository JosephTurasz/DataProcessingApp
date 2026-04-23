from __future__ import annotations
from PySide6.QtWidgets import QAbstractItemView, QTableView, QHeaderView, QLineEdit
from PySide6.QtCore import Qt, QRect, QPoint, QTimer, QEvent
from PySide6.QtGui import QDrag, QPainter, QColor, QCursor

from config.constants import TABLE_SCROLL_MARGIN_PX, TABLE_SCROLL_INTERVAL_MS


class EditableHeaderView(QHeaderView):
    """Horizontal header that supports inline column renaming."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self._editor: QLineEdit | None = None
        self._editing_section: int = -1
        self.sectionDoubleClicked.connect(self.start_inline_edit)

    def start_inline_edit(self, section: int) -> None:
        if self._editor is not None:
            self._cancel_edit()
        if section < 0:
            return

        current = self.model().headerData(section, self.orientation(), Qt.ItemDataRole.DisplayRole)

        editor = QLineEdit(self.viewport())
        editor.setText(str(current or ""))
        editor.selectAll()
        editor.setGeometry(self._section_viewport_rect(section))
        editor.show()
        editor.setFocus()
        editor.installEventFilter(self)

        editor.returnPressed.connect(lambda: self._commit_edit(section))
        editor.editingFinished.connect(lambda: self._commit_if_active(section))

        self._editor = editor
        self._editing_section = section

    def _section_viewport_rect(self, section: int) -> QRect:
        pos = self.sectionViewportPosition(section)
        size = self.sectionSize(section)
        vp = self.viewport()
        if self.orientation() == Qt.Orientation.Horizontal:
            return QRect(pos, 0, size, vp.height())
        return QRect(0, pos, vp.width(), size)

    def _commit_edit(self, section: int) -> None:
        if self._editor is None:
            return
        new_name = self._editor.text().strip()
        editor = self._editor
        self._editor = None
        self._editing_section = -1
        editor.blockSignals(True)
        editor.close()
        if new_name:
            model = self.model()
            if model and hasattr(model, "rename_column"):
                model.rename_column(section, new_name)

    def _commit_if_active(self, section: int) -> None:
        if self._editor is not None:
            self._commit_edit(section)

    def _cancel_edit(self) -> None:
        if self._editor is not None:
            editor = self._editor
            self._editor = None
            self._editing_section = -1
            editor.blockSignals(True)
            editor.close()

    def eventFilter(self, obj, event):
        if obj is self._editor and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_edit()
                return True
        return super().eventFilter(obj, event)

class DragDropTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeader(EditableHeaderView(Qt.Orientation.Horizontal, self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setMouseTracking(True)
        self.preview_indexes: list = []
        self._drag_armed = False
        self._drag_in_progress = False
        self._grab_row_offset = 0
        self._grab_col_offset = 0
        try:
            self.verticalScrollBar().setSingleStep(self.verticalHeader().defaultSectionSize())
            self.horizontalScrollBar().setSingleStep(self.horizontalHeader().defaultSectionSize())
        except Exception:
            pass

        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._auto_scroll_tick)
        
    def _selection_bounds(self):
        indexes = self.selectedIndexes()
        if not indexes:
            return None
        rows = [i.row() for i in indexes]
        cols = [i.column() for i in indexes]
        return min(rows), max(rows), min(cols), max(cols)

    def _selection_rect(self) -> QRect | None:
        b = self._selection_bounds()
        if not b:
            return None
        r0, r1, c0, c1 = b
        tl = self.visualRect(self.model().index(r0, c0))
        br = self.visualRect(self.model().index(r1, c1))
        return tl.united(br)

    def _update_drag_arming_and_cursor(self, pos: QPoint):
        rect = self._selection_rect()
        if rect is None:
            self._drag_armed = False
            self.unsetCursor()
            return

        if rect.contains(pos):
            self._drag_armed = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self._drag_armed = False
            self.unsetCursor()


    def _compute_target_top_left(self, hover_index):
        model = self.model()
        selected = self.selectedIndexes()
        if not selected:
            return hover_index.row(), hover_index.column(), 1, 1

        rows = sorted(set(i.row() for i in selected))
        cols = sorted(set(i.column() for i in selected))
        height = len(rows)
        width = len(cols)

        top_left_row = hover_index.row() - self._grab_row_offset
        top_left_col = hover_index.column() - self._grab_col_offset

        max_row = max(0, model.rowCount() - height)
        max_col = max(0, model.columnCount() - width)
        top_left_row = max(0, min(top_left_row, max_row))
        top_left_col = max(0, min(top_left_col, max_col))

        return top_left_row, top_left_col, height, width

    def _clamp_to_viewport(self, vp_pos: QPoint) -> QPoint:
        r = self.viewport().rect()
        x = min(max(vp_pos.x(), r.left()), r.right())
        y = min(max(vp_pos.y(), r.top()), r.bottom())
        return QPoint(x, y)

    def _update_preview_from_hover_index(self, index):
        model = self.model()
        selected = self.selectedIndexes()
        if not selected or model is None:
            self.clear_preview()
            return
        rows = sorted(set(i.row() for i in selected))
        cols = sorted(set(i.column() for i in selected))
        top_left_row, top_left_col, _, _ = self._compute_target_top_left(index)
        self.preview_indexes = [
            model.index(top_left_row + r_i, top_left_col + c_i)
            for r_i, _ in enumerate(rows)
            for c_i, _ in enumerate(cols)
            if (top_left_row + r_i < model.rowCount() and top_left_col + c_i < model.columnCount())]
        self.viewport().update()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.NoButton:
            self._update_drag_arming_and_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._drag_armed = False
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        self._update_drag_arming_and_cursor(pos)
        if self._drag_armed:
            grabbed = self.indexAt(pos)
            bounds = self._selection_bounds()
            if grabbed.isValid() and bounds:
                r0, r1, c0, c1 = bounds
                gr = max(r0, min(grabbed.row(), r1))
                gc = max(c0, min(grabbed.column(), c1))
                self._grab_row_offset = gr - r0
                self._grab_col_offset = gc - c0
            else:
                self._grab_row_offset = 0
                self._grab_col_offset = 0
        super().mousePressEvent(event)

    def startDrag(self, supportedActions):
        if not self._drag_armed:
            return
        indexes = self.selectedIndexes()
        if not indexes:
            return

        self._drag_in_progress = True
        if not self._scroll_timer.isActive():
            self._scroll_timer.start(TABLE_SCROLL_INTERVAL_MS)

        try:
            drag = QDrag(self)
            mime = self.model().mimeData(indexes)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._stop_auto_scroll()
            self.clear_preview()
            self._drag_in_progress = False

    def dragMoveEvent(self, event):
        vp_pos = event.position().toPoint()
        clamped = self._clamp_to_viewport(vp_pos)
        index = self.indexAt(clamped)
        if not index.isValid():
            self.clear_preview()
            return
        self._update_preview_from_hover_index(index)
        event.accept()

    def dropEvent(self, event):
        self._stop_auto_scroll()
        try:
            vp_pos = event.position().toPoint()
            index = self.indexAt(self._clamp_to_viewport(vp_pos))
            model = self.model()
            if not index.isValid() or model is None:
                event.ignore()
                return
            top_left_row, top_left_col, _, _ = self._compute_target_top_left(index)
            parent_index = model.index(top_left_row, top_left_col)
            if event.mimeData().hasFormat(model.MIME_TYPE):
                ok = model.dropMimeData(
                    event.mimeData(),
                    Qt.DropAction.MoveAction,
                    top_left_row,
                    top_left_col,
                    parent_index)
                if ok:
                    event.acceptProposedAction()
                else:
                    event.ignore()
            else:
                event.ignore()
        finally:
            self.clear_preview()
            self._drag_in_progress = False
            
    def _auto_scroll_tick(self):
        if not self._drag_in_progress:
            self._stop_auto_scroll()
            return
        vp_pos = self.viewport().mapFromGlobal(QCursor.pos())
        rect = self.viewport().rect()
        dx = 0
        dy = 0
        if vp_pos.x() < rect.left() + TABLE_SCROLL_MARGIN_PX:
            dx = -1
        elif vp_pos.x() > rect.right() - TABLE_SCROLL_MARGIN_PX:
            dx = 1

        if vp_pos.y() < rect.top() + TABLE_SCROLL_MARGIN_PX:
            dy = -1
        elif vp_pos.y() > rect.bottom() - TABLE_SCROLL_MARGIN_PX:
            dy = 1
        if dx:
            h = self.horizontalScrollBar()
            step = max(1, h.singleStep())
            h.setValue(h.value() + dx * step)
        if dy:
            v = self.verticalScrollBar()
            step = max(1, v.singleStep())
            v.setValue(v.value() + dy * step)
        clamped = self._clamp_to_viewport(vp_pos)
        idx = self.indexAt(clamped)
        if idx.isValid():
            self._update_preview_from_hover_index(idx)
        else:
            self.viewport().update()

    def _stop_auto_scroll(self):
        if self._scroll_timer.isActive():
            self._scroll_timer.stop()
            
    def start_header_rename(self, col: int) -> None:
        header = self.horizontalHeader()
        if isinstance(header, EditableHeaderView):
            header.start_inline_edit(col)

    def clear_preview(self):
        if self.preview_indexes:
            self.preview_indexes = []
            self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.preview_indexes:
            return
        painter = QPainter(self.viewport())
        painter.setBrush(QColor(0, 120, 215, 50))
        painter.setPen(QColor(0, 120, 215))
        for idx in self.preview_indexes:
            rect = self.visualRect(idx)
            painter.drawRect(rect)