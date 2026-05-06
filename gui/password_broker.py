from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, Qt, QMutex, QWaitCondition
from PySide6.QtWidgets import QInputDialog, QLineEdit

class PasswordBroker(QObject):
    request = Signal(str)
    _cancel = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._response = None
        self._pending = False
        self._dialog: QInputDialog | None = None

        self.request.connect(self._on_request, Qt.ConnectionType.QueuedConnection)
        self._cancel.connect(self._on_cancel, Qt.ConnectionType.QueuedConnection)

    def get_password(self, prompt: str, timeout_ms: int = 60_000) -> str | None:
        self._mutex.lock()
        try:
            self._pending = True
            self._response = None
            self.request.emit(prompt)

            while self._pending:
                if not self._wait.wait(self._mutex, timeout_ms):
                    self._pending = False
                    self._cancel.emit()
                    return None
            return self._response
        finally:
            self._mutex.unlock()

    @Slot()
    def _on_cancel(self):
        if self._dialog is not None:
            self._dialog.reject()

    @Slot(str)
    def _on_request(self, prompt: str):
        self._dialog = QInputDialog()
        self._dialog.setWindowTitle("Password required")
        self._dialog.setLabelText(prompt)
        self._dialog.setTextEchoMode(QLineEdit.EchoMode.Password)

        ok = bool(self._dialog.exec())
        response = self._dialog.textValue() if ok else None
        self._dialog = None

        self._mutex.lock()
        try:
            self._response = response
            self._pending = False
            self._wait.wakeAll()
        finally:
            self._mutex.unlock()
