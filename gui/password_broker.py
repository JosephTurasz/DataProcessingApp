from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, Qt, QMutex, QWaitCondition
from PySide6.QtWidgets import QInputDialog, QLineEdit

class PasswordBroker(QObject):
    request = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._response = None
        self._pending = False

        self.request.connect(self._on_request, Qt.ConnectionType.QueuedConnection)

    def get_password(self, prompt: str, timeout_ms: int = 60_000) -> str | None:
        self._mutex.lock()
        try:
            self._pending = True
            self._response = None
            self.request.emit(prompt)

            while self._pending:
                if not self._wait.wait(self._mutex, timeout_ms):
                    self._pending = False
                    return None
            return self._response
        finally:
            self._mutex.unlock()

    @Slot(str)
    def _on_request(self, prompt: str):
        pw, ok = QInputDialog.getText(None, "Password required", prompt, QLineEdit.EchoMode.Password)
        response = pw if ok else None

        self._mutex.lock()
        try:
            self._response = response
            self._pending = False
            self._wait.wakeAll()
        finally:
            self._mutex.unlock()
