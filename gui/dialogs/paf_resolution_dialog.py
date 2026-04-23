from __future__ import annotations

import pandas as pd

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel,QPushButton, QHBoxLayout, QMessageBox

from gui.tables.paf_resolution_table import PAFResolutionTable

class PAFResolutionDialog(QDialog):
    def __init__(self,current_postcodes,issue_labels,row_previews,*,preview_specs,postcode_column,town_column,normalizer,parent=None):
        super().__init__(parent)

        self.setWindowTitle("Resolve PAF Fields")
        self.resize(950, 280)

        self.current_postcodes = list(current_postcodes)
        self.issue_labels = list(issue_labels or [])
        self.row_previews = [dict(r or {}) for r in row_previews]
        self.preview_specs = list(preview_specs or [])
        self.postcode_column = str(postcode_column)
        self.town_column = str(town_column)
        self.normalizer = normalizer

        self.preview_to_source = {str(spec["preview"]): str(spec["source"])for spec in self.preview_specs}
        self.source_to_preview = {str(spec["source"]): str(spec["preview"])for spec in self.preview_specs}
        self.postcode_preview_column = self.source_to_preview.get(self.postcode_column, self.postcode_column)
        self.town_preview_column = self.source_to_preview.get(self.town_column, self.town_column)

        self.index = 0

        self.corrected = {}
        self.added = {}
        self.removed = set()
        self.row_updates = {}
        self.history = []

        self.layout = QVBoxLayout(self)

        self.position_label = QLabel()
        self.layout.addWidget(self.position_label)

        self.issue_label = QLabel()
        self.layout.addWidget(self.issue_label)

        self.current_postcode_label = QLabel()
        self.layout.addWidget(self.current_postcode_label)

        self.address_table = PAFResolutionTable()
        self.layout.addWidget(self.address_table)

        btn_row = QHBoxLayout()

        self.update_btn = QPushButton("Update")
        btn_row.addWidget(self.update_btn)

        self.add_btn = QPushButton("Add to Database")
        btn_row.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove")
        btn_row.addWidget(self.remove_btn)

        self.layout.addLayout(btn_row)

        undo_row = QHBoxLayout()
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setEnabled(False)
        undo_row.addWidget(self.undo_btn)
        undo_row.addStretch()
        self.layout.addLayout(undo_row)

        self.update_btn.clicked.connect(self._update_record)
        self.add_btn.clicked.connect(self._add_postcode_to_database)
        self.remove_btn.clicked.connect(self._remove_record)
        self.undo_btn.clicked.connect(self._undo)

        self._load()

    def _load(self):
        current_pc = self.current_postcodes[self.index] if self.index < len(self.current_postcodes) else ""
        issue = self.issue_labels[self.index] if self.index < len(self.issue_labels) else "Review"

        self.position_label.setText(f"Record {self.index + 1} of {len(self.row_previews)}")
        self.issue_label.setText(f"Issue: {issue}")
        self.current_postcode_label.setText(f"Current postcode: {current_pc}")
        self.undo_btn.setEnabled(bool(self.history))

        self._load_preview_table()

    def _load_preview_table(self):
        preview = self.row_previews[self.index] if self.index < len(self.row_previews) else {}

        if not preview:
            self.address_table.set_preview_dataframe(pd.DataFrame([{}]))
            self.address_table.setFixedHeight(30)
            return

        df = pd.DataFrame([preview])
        self.address_table.set_preview_dataframe(df)

        try:
            self.address_table.resizeColumnsToContents()
            self.address_table.resizeRowsToContents()
        except Exception:
            pass

        model = self.address_table.model()
        if model is not None and model.rowCount() > 0:
            row_height = self.address_table.rowHeight(0)
            header_height = self.address_table.horizontalHeader().height()
            self.address_table.setFixedHeight(row_height + header_height + 6)
        else:
            self.address_table.setFixedHeight(30)

    def _current_table_preview_values(self) -> dict[str, str]:
        df = self.address_table.dataframe()
        if df.empty:
            return {}

        row = df.iloc[0].to_dict()
        return {str(k): "" if pd.isna(v) else str(v) for k, v in row.items()}

    def _preview_values_to_source_values(self, preview_values: dict[str, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for preview_col, value in preview_values.items():
            source_col = self.preview_to_source.get(preview_col)
            if source_col:
                out[source_col] = value
        return out

    def _extract_postcode_from_preview_row(self, preview_values: dict[str, str]) -> str:
        value = preview_values.get(self.postcode_preview_column, "")
        return str(value).strip()

    def _extract_town_from_preview_row(self, preview_values: dict[str, str]) -> str:
        value = preview_values.get(self.town_preview_column, "")
        return str(value).strip()

    def _record_history(self, idx: int):
        self.history.append({"idx": idx,"prev_corrected": self.corrected.get(idx),"prev_added": self.added.get(idx),
                             "prev_removed": idx in self.removed,"prev_row_preview": dict(self.row_previews[idx]) if idx < len(self.row_previews) else {},
                             "prev_row_update": dict(self.row_updates[idx]) if idx in self.row_updates else None,})
        self.undo_btn.setEnabled(True)

    def _update_record(self):
        idx = self.index
        edited_preview_row = self._current_table_preview_values()
        postcode = self._extract_postcode_from_preview_row(edited_preview_row)
        town = self._extract_town_from_preview_row(edited_preview_row)

        if not postcode:
            QMessageBox.warning(self, "Error", "Postcode cannot be blank.")
            return

        if not town:
            QMessageBox.warning(self, "Error", "Town cannot be blank.")
            return

        self._record_history(idx)

        self.row_previews[idx] = dict(edited_preview_row)
        self.row_updates[idx] = self._preview_values_to_source_values(edited_preview_row)

        self.corrected[idx] = postcode
        self.added.pop(idx, None)
        self.removed.discard(idx)

        self._next()

    def _add_postcode_to_database(self):
        edited_preview_row = self._current_table_preview_values()
        postcode = self._extract_postcode_from_preview_row(edited_preview_row)
        town = self._extract_town_from_preview_row(edited_preview_row)

        if not postcode:
            QMessageBox.warning(self, "Error", "Postcode cannot be blank.")
            return

        if not town:
            QMessageBox.warning(self, "Error", "Town cannot be blank.")
            return

        idx = self.index
        self._record_history(idx)

        norm = self.normalizer(postcode)
        self.row_previews[idx] = dict(edited_preview_row)
        self.row_updates[idx] = self._preview_values_to_source_values(edited_preview_row)

        self.added[idx] = norm
        self.corrected.pop(idx, None)
        self.removed.discard(idx)

        self._next()

    def _remove_record(self):
        idx = self.index
        self._record_history(idx)

        self.removed.add(idx)
        self.corrected.pop(idx, None)
        self.added.pop(idx, None)
        self.row_updates.pop(idx, None)

        self._next()

    def _undo(self):
        if not self.history:
            return
        state = self.history.pop()
        idx = state["idx"]

        if state["prev_corrected"] is None:
            self.corrected.pop(idx, None)
        else:
            self.corrected[idx] = state["prev_corrected"]

        if state["prev_added"] is None:
            self.added.pop(idx, None)
        else:
            self.added[idx] = state["prev_added"]

        if state["prev_removed"]:
            self.removed.add(idx)
        else:
            self.removed.discard(idx)

        self.row_previews[idx] = dict(state["prev_row_preview"])

        if state["prev_row_update"] is None:
            self.row_updates.pop(idx, None)
        else:
            self.row_updates[idx] = dict(state["prev_row_update"])

        self.index = idx
        self._load()
        self.undo_btn.setEnabled(bool(self.history))

    def _next(self):
        if self.index < len(self.row_previews) - 1:
            self.index += 1
            self._load()
        else:
            self.accept()

    def result(self):
        return {"corrected": self.corrected,"added": self.added,"removed": self.removed,"row_updates": self.row_updates,}