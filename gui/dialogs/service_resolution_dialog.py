from __future__ import annotations

from PySide6.QtWidgets import QComboBox,QDialog,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QPushButton,QVBoxLayout

from gui.tables.service_resolution_table import ServiceResolutionTable

class ServiceResolutionDialog(QDialog):
    def __init__(self, rows, valid_services, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Resolve Services")
        self.resize(1100, 550)

        self._rows = [dict(r or {}) for r in rows]
        self._valid_services = [str(v).strip() for v in (valid_services or []) if str(v).strip()]

        layout = QVBoxLayout(self)

        self.count_label = QLabel(f"Rows requiring review: {len(self._rows)}")
        layout.addWidget(self.count_label)

        self.table = ServiceResolutionTable()
        self.table.set_rows(self._rows)
        layout.addWidget(self.table, 1)

        mass_group = QGroupBox("Mass Update Functions")
        mass_layout = QHBoxLayout(mass_group)

        mass_layout.addWidget(QLabel("Service:"))

        self.service_combo = QComboBox()
        self.service_combo.addItem("")
        self.service_combo.addItems(self._valid_services)
        mass_layout.addWidget(self.service_combo, 2)

        mass_layout.addWidget(QLabel("Length:"))
        self.length_edit = QLineEdit()
        self.length_edit.setPlaceholderText("Ignore if blank")
        mass_layout.addWidget(self.length_edit, 1)

        mass_layout.addWidget(QLabel("Width:"))
        self.width_edit = QLineEdit()
        self.width_edit.setPlaceholderText("Ignore if blank")
        mass_layout.addWidget(self.width_edit, 1)

        mass_layout.addWidget(QLabel("Height:"))
        self.height_edit = QLineEdit()
        self.height_edit.setPlaceholderText("Ignore if blank")
        mass_layout.addWidget(self.height_edit, 1)

        mass_layout.addWidget(QLabel("Weight:"))
        self.weight_edit = QLineEdit()
        self.weight_edit.setPlaceholderText("Ignore if blank")
        mass_layout.addWidget(self.weight_edit, 1)

        layout.addWidget(mass_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_update = QPushButton("Update")
        btn_row.addWidget(self.btn_update)

        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_cancel)

        layout.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_update.clicked.connect(self.accept)

    def result_rows(self) -> list[dict[str, str]]:
        return self.table.rows()

    def mass_update_values(self) -> dict[str, str]:
        return {"Service": self.service_combo.currentText().strip(),
                "Length": self.length_edit.text().strip(),
                "Width": self.width_edit.text().strip(),
                "Height": self.height_edit.text().strip(),
                "Weight": self.weight_edit.text().strip()}