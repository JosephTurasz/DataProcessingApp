from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from gui.tables.field_length_resolution_table import FieldLengthResolutionTable


class FieldLengthResolutionDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Field Length Warning")
        self.resize(1200, 550)

        self._action = "continue"

        layout = QVBoxLayout(self)

        self.count_label = QLabel(
            f"Rows with fields longer than 35 characters: {len(rows)}"
        )
        layout.addWidget(self.count_label)

        self.info_label = QLabel(
            "These values may be truncated on the label but can still be uploaded. "
            "You can edit them now or continue without changes."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.table = FieldLengthResolutionTable()
        self.table.set_rows(rows)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_update = QPushButton("Update")
        self.btn_continue = QPushButton("Continue Anyway")
        self.btn_cancel = QPushButton("Cancel")

        btn_row.addWidget(self.btn_update)
        btn_row.addWidget(self.btn_continue)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.btn_update.clicked.connect(self._accept_update)
        self.btn_continue.clicked.connect(self._accept_continue)
        self.btn_cancel.clicked.connect(self.reject)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.table.resizeRowsToContents()

    def _accept_update(self) -> None:
        self._action = "update"
        self.accept()

    def _accept_continue(self) -> None:
        self._action = "continue"
        self.accept()

    def dialog_action(self) -> str:
        return self._action

    def result_rows(self) -> list[dict[str, str]]:
        return self.table.rows()