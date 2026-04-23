from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,QPushButton,QRadioButton,QLineEdit,QGroupBox,QMessageBox,QToolButton

class DropArea(QWidget):
    pathsDropped = Signal(list)

    def __init__(self, text: str = "Drop files/folders to zip", min_height: int = 160):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(int(min_height))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("zipDropArea")

        self._label = QLabel(text, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: transparent; border: none;")

        lay = QVBoxLayout(self)
        lay.addWidget(self._label)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(16, 16, 16, 16)

        self._label.installEventFilter(self)
        self._set_normal_style()
    # ---------- styling ----------
    def _set_normal_style(self):
        self.setStyleSheet("QWidget#zipDropArea {border: 2px dashed #888;border-radius: 10px;background: transparent;}")

    def _set_hover_style(self):
        self.setStyleSheet("QWidget#zipDropArea {border: 2px dashed #2a82da;border-radius: 10px;background: rgba(42, 130, 218, 20);}")
    # ---------- event filter ----------
    def eventFilter(self, watched, event):
        et = event.type()
        if et == event.Type.DragEnter:
            return self._handle_drag_enter(event)
        if et == event.Type.DragMove:
            return self._handle_drag_move(event)
        if et == event.Type.DragLeave:
            return self._handle_drag_leave(event)
        if et == event.Type.Drop:
            return self._handle_drop(event)
        return super().eventFilter(watched, event)
    # ---------- main drag/drop handlers ----------
    def dragEnterEvent(self, event):
        self._handle_drag_enter(event)

    def dragMoveEvent(self, event):
        self._handle_drag_move(event)

    def dragLeaveEvent(self, event):
        self._handle_drag_leave(event)

    def dropEvent(self, event):
        self._handle_drop(event)

    def _handle_drag_enter(self, event):
        if event.mimeData().hasUrls():
            self._set_hover_style()
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def _handle_drag_move(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def _handle_drag_leave(self, event):
        self._set_normal_style()
        event.accept()
        return True

    def _handle_drop(self, event):
        self._set_normal_style()

        urls = event.mimeData().urls() or []
        paths: list[str] = []
        for u in urls:
            if u.isLocalFile():
                p = u.toLocalFile()
                if p:
                    paths.append(os.path.normpath(p))

        seen = set()
        cleaned: list[str] = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                cleaned.append(p)

        if cleaned:
            self.pathsDropped.emit(cleaned)

        event.acceptProposedAction()
        return True

class ZipDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Zip")
        self.resize(650, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._paths: list[str] = []

        root = QVBoxLayout(self)
        # ---- Password ----
        pw_box = QGroupBox("Password")
        pw_lay = QVBoxLayout(pw_box)

        mode_row = QHBoxLayout()
        self.rb_random = QRadioButton("Generate random password")
        self.rb_enter = QRadioButton("Enter password")
        self.rb_none = QRadioButton("No password")
        self.rb_random.setChecked(True)

        mode_row.addWidget(self.rb_random)
        mode_row.addWidget(self.rb_enter)
        mode_row.addWidget(self.rb_none)
        mode_row.addStretch()
        pw_lay.addLayout(mode_row)

        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_edit.setPlaceholderText("Password…")
        pw_lay.addWidget(self.pw_edit)

        def refresh_pw_state():
            self.pw_edit.setEnabled(self.rb_enter.isChecked())
            if not self.rb_enter.isChecked():
                self.pw_edit.setText("")

        self.rb_random.toggled.connect(refresh_pw_state)
        self.rb_enter.toggled.connect(refresh_pw_state)
        self.rb_none.toggled.connect(refresh_pw_state)
        refresh_pw_state()

        root.addWidget(pw_box)
        # ---- Drop zone + list ----
        self.drop = DropArea(min_height=160)
        self.list = QListWidget()

        root.addWidget(self.drop, 2)
        root.addWidget(self.list, 1)

        tools = QHBoxLayout()
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_paths)

        self.btn_remove = QToolButton()
        self.btn_remove.setText("Remove selected")
        self.btn_remove.clicked.connect(self._remove_selected)

        tools.addWidget(self.btn_clear)
        tools.addWidget(self.btn_remove)
        tools.addStretch()
        root.addLayout(tools)
        
        # ---- Buttons ----
        bottom = QHBoxLayout()
        bottom.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_go = QPushButton("Go")
        self.btn_go.setDefault(True)
        self.btn_go.setEnabled(False)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_go.clicked.connect(self._on_go)

        bottom.addWidget(self.btn_cancel)
        bottom.addWidget(self.btn_go)
        root.addLayout(bottom)

        self.drop.pathsDropped.connect(self._add_paths)

    def _add_paths(self, paths: list[str]):
        existing = set(self._paths)
        for p in paths:
            if p not in existing:
                self._paths.append(p)
                self.list.addItem(p)
                existing.add(p)
        self.btn_go.setEnabled(len(self._paths) > 0)

    def _clear_paths(self):
        self._paths = []
        self.list.clear()
        self.btn_go.setEnabled(False)

    def _remove_selected(self):
        items = self.list.selectedItems()
        if not items:
            return
        to_remove = {it.text() for it in items}
        self._paths = [p for p in self._paths if p not in to_remove]
        self.list.clear()
        for p in self._paths:
            self.list.addItem(p)
        self.btn_go.setEnabled(len(self._paths) > 0)

    def _on_go(self):
        if not self._paths:
            return

        if self.rb_enter.isChecked():
            pw = (self.pw_edit.text() or "").strip()
            if not pw:
                QMessageBox.warning(self,"Missing password","Password is blank.")
                return
        self.accept()

    def get_result(self) -> dict:
        if self.rb_random.isChecked():
            mode = "random"
        elif self.rb_enter.isChecked():
            mode = "enter"
        else:
            mode = "none"

        return {"paths": list(self._paths),"password_mode": mode,"password": (self.pw_edit.text() or "").strip()}