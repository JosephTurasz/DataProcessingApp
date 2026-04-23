from __future__ import annotations

from PySide6.QtWidgets import QDialog,QHBoxLayout,QLabel,QPushButton,QVBoxLayout

from gui.tables.recipient_name_resolution_table import RecipientNameResolutionTable

class RecipientNameResolutionDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Resolve Recipient Names")
        self.resize(900, 500)

        self._rows = [dict(r or {}) for r in rows]
        self._removed: set[int] = set()
        # Tracks which original index each currently-visible row corresponds to.
        # Must be updated on every removal so visual positions stay stable.
        self._visible_originals: list[int] = list(range(len(self._rows)))

        layout = QVBoxLayout(self)

        self.count_label = QLabel(f"Rows requiring review: {len(self._rows)}")
        layout.addWidget(self.count_label)

        self.table = RecipientNameResolutionTable()
        self.table.set_rows(self._rows)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()

        self.btn_remove = QPushButton("Remove Selected")
        btn_row.addWidget(self.btn_remove)

        btn_row.addStretch()

        self.btn_update = QPushButton("Update")
        btn_row.addWidget(self.btn_update)

        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_cancel)

        layout.addLayout(btn_row)

        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_update.clicked.connect(self.accept)

    def _remove_selected(self) -> None:
        selected_visual = self.table.selected_row_indices()
        if not selected_visual:
            return

        # Map current visual positions to original indices before storing.
        # Without this, a second removal compares new visual indices against
        # original-table indices and drops the wrong rows.
        for vis_idx in selected_visual:
            if vis_idx < len(self._visible_originals):
                self._removed.add(self._visible_originals[vis_idx])

        self._visible_originals = [i for i in self._visible_originals if i not in self._removed]
        kept_rows = [self._rows[i] for i in self._visible_originals]

        self.table.set_rows(kept_rows)
        self.count_label.setText(f"Rows requiring review: {len(kept_rows)}")

        if not kept_rows:
            self.accept()

    def result_rows(self) -> list[dict[str, str]]:
        return self.table.rows()

    def removed_indices(self) -> set[int]:
        return set(self._removed)