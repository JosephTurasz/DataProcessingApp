from __future__ import annotations

import math
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout

from config.constants import SYSTEM_PRINTERS

class BatchPdfPrintDialog(QDialog):
    print_requested = Signal()
    skip_requested = Signal()

    def __init__(self, pdf_list: list[str], parent=None):
        super().__init__(parent)

        self.pdf_list = pdf_list
        self.batch_index = 0
        self.batch_size = len(SYSTEM_PRINTERS)

        self.setWindowTitle("Print Files")
        self.resize(360, 280)

        self.layout = QVBoxLayout(self)

        self.lbl_header = QLabel("Files Loaded:")
        self.layout.addWidget(self.lbl_header)

        self.file_list_widget = QListWidget()
        self.layout.addWidget(self.file_list_widget)

        total_batches = self.total_batches()
        self.lbl_status = QLabel(f"Batch 1 / {total_batches}")
        self.layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_skip = QPushButton("Skip")
        self.btn_next = QPushButton("Print && Next")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_next)
        self.layout.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        self.btn_next.clicked.connect(self.print_requested.emit)

        self.refresh()
    # ---------- batch helpers ----------
    def total_batches(self) -> int:
        return max(1, math.ceil(len(self.pdf_list) / self.batch_size))

    def current_batch_number(self) -> int:
        return min(self.total_batches(), math.ceil((self.batch_index + 1) / self.batch_size) or 1)

    def is_finished(self) -> bool:
        return self.batch_index >= len(self.pdf_list)

    def current_batch_files(self) -> list[str]:
        return self.pdf_list[self.batch_index:self.batch_index + self.batch_size]

    def advance_batch(self) -> None:
        self.batch_index += self.batch_size
        self.refresh()

    def skip_batch(self) -> None:
        self.advance_batch()

    # ---------- UI updates ----------
    def set_controls_enabled(self, enabled: bool) -> None:
        self.btn_next.setEnabled(enabled)
        self.btn_skip.setEnabled(enabled)
        self.btn_cancel.setEnabled(enabled)

    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def refresh(self) -> None:
        self.file_list_widget.clear()
        for f in self.current_batch_files():
            self.file_list_widget.addItem(os.path.basename(f))

        if self.is_finished():
            self.lbl_status.setText("Finished")
            return

        self.lbl_status.setText(f"Batch {self.current_batch_number()} / {self.total_batches()}")
        self._update_button_label()

    def _update_button_label(self) -> None:
        remaining = len(self.pdf_list) - self.batch_index
        self.btn_next.setText("Print && Finish" if remaining <= self.batch_size else "Print && Next")
