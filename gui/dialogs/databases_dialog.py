from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from openpyxl import Workbook

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

if TYPE_CHECKING:
    from processing.repos.login_repo import LoginRepository
    from processing.repos.seeds_repo import SeedsRepository
    from processing.repos.ecom_services_repo import EcomServicesRepository
    from processing.repos.mailsort_services_repo import MailsortServicesRepository
    from processing.repos.return_addresses_repo import ReturnAddressesRepository
    from processing.repos.ucids_repo import UcidsRepository


def _make_readonly_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return it

def _make_editable_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
    return it

def _make_readonly_id_item(value: int) -> QTableWidgetItem:
    it = QTableWidgetItem()
    it.setData(Qt.ItemDataRole.DisplayRole, int(value))
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return it

def _get_cell_text(table: QTableWidget, r: int, c: int) -> str:
    it = table.item(r, c)
    return (it.text() if it else "").strip()

class QueryDatabasesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Databases")

        root = QVBoxLayout(self)

        tabs = QTabWidget()
        root.addWidget(tabs)

        s = parent.s

        tabs.addTab(_LoginBrowserTab(repo=s.mailmark_logins_repo, export_name="Mailmark logins", parent=self), "Mailmark logins")
        tabs.addTab(_LoginBrowserTab(repo=s.mixed_weight_logins_repo, export_name="Mixed weight logins", parent=self), "Mixed weight logins")
        tabs.addTab(_SeedsBrowserTab(repo=s.seeds_repo, parent=self), "Seeds")
        tabs.addTab(_MailsortServicesBrowserTab(repo=s.mailsort_services_repo, parent=self), "Mailsort Services")
        tabs.addTab(_ServicesBrowserTab(repo=s.ecom_services_repo, parent=self), "Ecom Services")
        tabs.addTab(_ReturnAddressesBrowserTab(repo=s.return_addresses_repo, parent=self), "Return Addresses")
        tabs.addTab(_UcidsBrowserTab(repo=s.ucids_repo, parent=self), "UCIDs")

        tabs.setCurrentIndex(0)
        self.resize(1040, 720)

class _BaseBrowserTab(QWidget):
    def __init__(
        self,
        *,
        repo,
        placeholder_text: str,
        headers: list[str],
        query_error_title: str,
        stretch_last_section: bool,
        export_name: str = "database_export",
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self._new_row_indices: list[int] = []
        self._headers = headers
        self._query_error_title = query_error_title
        self._export_name = str(export_name or "database_export")

        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder_text)
        bar.addWidget(self.edit, 1)

        self.btn_go = QPushButton("Go")
        self.btn_clear = QPushButton("Clear")
        bar.addWidget(self.btn_go)
        bar.addWidget(self.btn_clear)
        root.addLayout(bar)

        self.lbl_status = QLabel("")
        root.addWidget(self.lbl_status)

        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(stretch_last_section)

        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_export = QPushButton("Export")
        self.btn_delete = QPushButton("Delete row")
        self.btn_add = QPushButton("Add row")
        self.btn_exec = QPushButton("Execute")
        bottom.addWidget(self.btn_export)
        bottom.addWidget(self.btn_delete)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_add)
        bottom.addWidget(self.btn_exec)
        root.addLayout(bottom)

        self.btn_go.clicked.connect(self._apply_filter)
        self.btn_clear.clicked.connect(self._clear_filter)
        self.edit.returnPressed.connect(self._apply_filter)
        self.btn_export.clicked.connect(self._export_xlsx)
        self.btn_delete.clicked.connect(self._delete_selected_row)
        self.btn_add.clicked.connect(self._add_row)
        self.btn_exec.clicked.connect(self._execute_inserts)

        self._load_all()

    def _set_rows(self, rows: list[dict]):
        self._new_row_indices.clear()

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for r_i, row in enumerate(rows):
                values = self._row_to_display_values(row)
                for c, value in enumerate(values):
                    if c == 0:
                        self.table.setItem(r_i, c, _make_readonly_id_item(int(value or 0)))
                    else:
                        self.table.setItem(r_i, c, _make_readonly_item("" if value is None else str(value)))

            self.lbl_status.setText(f"Rows: {len(rows)}")
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.table.resizeColumnsToContents()

    def _load_all(self):
        try:
            rows = self._list_all_rows()
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, self._query_error_title, str(e))

    def _apply_filter(self):
        q = (self.edit.text() or "").strip()
        try:
            rows = self._search_rows(q)
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, self._query_error_title, str(e))

    def _clear_filter(self):
        self.edit.setText("")
        self._load_all()

    def _export_xlsx(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Export", "There are no rows to export.")
            return

        safe_name = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in self._export_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export database",
            f"{safe_name}.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Export"

            headers = []
            for c in range(self.table.columnCount()):
                item = self.table.horizontalHeaderItem(c)
                headers.append("" if item is None else item.text())
            ws.append(headers)

            for r in range(self.table.rowCount()):
                row_values = []
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    if item is None:
                        row_values.append("")
                        continue

                    if c == 0:
                        value = item.data(Qt.ItemDataRole.DisplayRole)
                        row_values.append("" if value is None else value)
                    else:
                        row_values.append(item.text())
                ws.append(row_values)

            for col_cells in ws.columns:
                max_len = 0
                col_letter = col_cells[0].column_letter
                for cell in col_cells:
                    value = "" if cell.value is None else str(cell.value)
                    if len(value) > max_len:
                        max_len = len(value)
                ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

            wb.save(path)
            QMessageBox.information(self, "Export", f"Exported to:\n{path}")

        except Exception as e:
            QMessageBox.critical(self, "Export", f"Export failed:\n{e}")
    
    def _add_row(self):
        try:
            db_next_id = self._next_id()
        except Exception as e:
            QMessageBox.critical(self, "Add row", f"Could not determine next ID:\n{e}")
            return

        next_id = db_next_id

        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if not item:
                continue
            try:
                row_id = int(item.data(Qt.ItemDataRole.DisplayRole))
                if row_id >= next_id:
                    next_id = row_id + 1
            except Exception:
                continue

        self.table.setSortingEnabled(False)

        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, _make_readonly_id_item(next_id))

        for c in range(1, len(self._headers)):
            self.table.setItem(r, c, _make_editable_item(""))

        self._new_row_indices.append(r)
        self.table.resizeColumnsToContents()
        self.table.setCurrentCell(r, 1)
        self.table.editItem(self.table.item(r, 1))

    def _execute_inserts(self):
        if not self._new_row_indices:
            QMessageBox.information(self, "Execute", "No new rows to insert.")
            return

        try:
            payloads = [self._extract_payload(r) for r in list(self._new_row_indices)]
        except ValueError as e:
            QMessageBox.critical(self, "Execute", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Execute", f"Insert preparation failed:\n{e}")
            return

        try:
            self._insert_payloads(payloads)
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Execute", f"DB constraint error:\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Execute", f"Insert failed:\n{e}")
            return

        QMessageBox.information(self, "Execute", f"Inserted {len(payloads)} row(s).")
        self._load_all()

    def _selected_row_index(self) -> int | None:
        row = self.table.currentRow()
        return row if row >= 0 else None

    def _delete_selected_row(self):
        row = self._selected_row_index()
        if row is None:
            QMessageBox.information(self, "Delete row", "No row selected.")
            return

        try:
            row_id = self._row_id_from_table(row)
        except Exception as e:
            QMessageBox.critical(self, "Delete row", str(e))
            return

        confirm = QMessageBox.question(
            self,
            "Delete row",
            f"Delete row with ID {row_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            if row in self._new_row_indices:
                self.table.removeRow(row)
                self._new_row_indices = [
                    r - 1 if r > row else r
                    for r in self._new_row_indices
                    if r != row
                ]
                self.lbl_status.setText(f"Rows: {self.table.rowCount()}")
                return

            self._delete_row_by_id(row_id)
        except Exception as e:
            QMessageBox.critical(self, "Delete row", f"Delete failed:\n{e}")
            return

        QMessageBox.information(self, "Delete row", "Row deleted.")
        self._load_all()

    def _delete_row_by_id(self, row_id: int):
        raise NotImplementedError

    def _row_id_from_table(self, r: int) -> int:
        id_item = self.table.item(r, 0)
        id_val = id_item.data(Qt.ItemDataRole.DisplayRole) if id_item else None
        try:
            return int(id_val)
        except Exception as e:
            raise ValueError(f"Row {r + 1}: invalid ID.") from e

    def _list_all_rows(self) -> list[dict]:
        raise NotImplementedError

    def _search_rows(self, q: str) -> list[dict]:
        raise NotImplementedError

    def _next_id(self) -> int:
        raise NotImplementedError

    def _row_to_display_values(self, row: dict) -> list:
        raise NotImplementedError

    def _extract_payload(self, r: int):
        raise NotImplementedError

    def _insert_payloads(self, payloads: list):
        raise NotImplementedError

class _LoginBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: LoginRepository, export_name: str, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search name/username...",
            headers=["ID", "Name", "Username", "Password"],
            query_error_title="Query logins",
            stretch_last_section=True,
            export_name=export_name,
            parent=parent,
        )

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [row.get("ID", 0), row.get("Name", ""), row.get("Username", ""), row.get("Password", "")]

    def _extract_payload(self, r: int):
        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for id_int, name, username, password in payloads:
                cur.execute(
                    f"INSERT INTO {self.repo.table_name} (ID, Name, Username, Password) VALUES (?, ?, ?, ?)",
                    (id_int, name, username, password),
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute(f"DELETE FROM {self.repo.table_name} WHERE ID = ?", (int(row_id),))
            cur.execute(f"UPDATE {self.repo.table_name} SET ID = ID - 1 WHERE ID > ?", (int(row_id),))
            con.commit()

class _SeedsBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: SeedsRepository, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search key/category/name...",
            headers=["ID", "KEY", "Category", "Name", "Address 1", "Address 2", "Town", "Postcode", "DPS"],
            query_error_title="Query seeds",
            stretch_last_section=False,
            export_name="Seeds",
            parent=parent,
        )

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all_rows()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search_rows(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [
            row.get("ID", 0),
            row.get("KEY", ""),
            row.get("Category", ""),
            row.get("Name", ""),
            row.get("Address_1", ""),
            row.get("Address_2", ""),
            row.get("Town", ""),
            row.get("Postcode", ""),
            row.get("DPS", ""),
        ]

    def _extract_payload(self, r: int):
        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
            _get_cell_text(self.table, r, 4),
            _get_cell_text(self.table, r, 5),
            _get_cell_text(self.table, r, 6),
            _get_cell_text(self.table, r, 7),
            _get_cell_text(self.table, r, 8),
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for id_int, key, category, name, address_1, address_2, town, postcode, dps in payloads:
                cur.execute(
                    "INSERT INTO Seeds (ID, KEY, Category, Name, Address_1, Address_2, Town, Postcode, DPS)"
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (id_int, key, category, name, address_1, address_2, town, postcode, dps),
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Seeds WHERE ID = ?", (int(row_id),))
            cur.execute("UPDATE Seeds SET ID = ID - 1 WHERE ID > ?", (int(row_id),))
            con.commit()

class _MailsortServicesBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: MailsortServicesRepository, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search service name/code/category...",
            headers=[
                "ID",
                "Service Name",
                "Format Code",
                "Sortation Code",
                "Machinability Code",
                "Format",
                "Sortation",
                "Machinability",
                "Mail Category",
            ],
            query_error_title="Query mailsort services",
            stretch_last_section=False,
            export_name="Mailsort Services",
            parent=parent,
        )

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [
            row.get("Id", 0),
            row.get("service_name", ""),
            row.get("format_code", ""),
            row.get("sortation_code", ""),
            row.get("machinability_code", ""),
            row.get("format", ""),
            row.get("sortation", ""),
            row.get("machinability", ""),
            row.get("mail_category", ""),
        ]

    def _extract_payload(self, r: int):
        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
            _get_cell_text(self.table, r, 4),
            _get_cell_text(self.table, r, 5),
            _get_cell_text(self.table, r, 6),
            _get_cell_text(self.table, r, 7),
            _get_cell_text(self.table, r, 8),
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for (id_int, service_name, format_code, sortation_code, machinability_code,
                 format, sortation, machinability, mail_category) in payloads:
                cur.execute(
                    f"""INSERT INTO {self.repo.table_name}
                        (Id, service_name, format_code, sortation_code, machinability_code,
                         format, sortation, machinability, mail_category)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (id_int, service_name, format_code, sortation_code, machinability_code,
                     format, sortation, machinability, mail_category),
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute(f"DELETE FROM {self.repo.table_name} WHERE Id = ?", (int(row_id),))
            cur.execute(f"UPDATE {self.repo.table_name} SET Id = Id - 1 WHERE Id > ?", (int(row_id),))
            con.commit()


class _ServicesBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: EcomServicesRepository, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search name/code...",
            headers=[
                "ID",
                "Name",
                "New Code",
                "Old Code",
                "Replacement Code",
                "Max Weight (g)",
                "Min Length (mm)",
                "Min Width (mm)",
                "Min Height (mm)",
                "Max Length (mm)",
                "Max Width (mm)",
                "Max Height (mm)",
            ],
            query_error_title="Query services",
            stretch_last_section=False,
            export_name="Services",
            parent=parent,
        )

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [
            row.get("id", 0),
            row.get("name", ""),
            row.get("new_code", ""),
            row.get("old_code", ""),
            row.get("replacement_code", ""),
            row.get("max_weight_g", ""),
            row.get("min_length_mm", ""),
            row.get("min_width_mm", ""),
            row.get("min_height_mm", ""),
            row.get("max_length_mm", ""),
            row.get("max_width_mm", ""),
            row.get("max_height_mm", ""),
        ]

    def _parse_optional_int(self, text: str) -> int | None:
        text = (text or "").strip()
        if not text:
            return None
        return int(text)

    def _extract_payload(self, r: int):
        try:
            max_weight_g = int(_get_cell_text(self.table, r, 5))
            min_length_mm = int(_get_cell_text(self.table, r, 6))
            min_width_mm = int(_get_cell_text(self.table, r, 7))
            min_height_mm = int(_get_cell_text(self.table, r, 8))
            max_length_mm = self._parse_optional_int(_get_cell_text(self.table, r, 9))
            max_width_mm = self._parse_optional_int(_get_cell_text(self.table, r, 10))
            max_height_mm = self._parse_optional_int(_get_cell_text(self.table, r, 11))
        except ValueError as e:
            raise ValueError(f"Row {r + 1}: numeric columns must contain valid integers.") from e

        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
            _get_cell_text(self.table, r, 4),
            max_weight_g,
            min_length_mm,
            min_width_mm,
            min_height_mm,
            max_length_mm,
            max_width_mm,
            max_height_mm,
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for (
                id_int,
                name,
                new_code,
                old_code,
                replacement_code,
                max_weight_g,
                min_length_mm,
                min_width_mm,
                min_height_mm,
                max_length_mm,
                max_width_mm,
                max_height_mm,
            ) in payloads:
                cur.execute(
                    f"""INSERT INTO {self.repo.table_name} (id,name,new_code,old_code,replacement_code,max_weight_g,min_length_mm,
                            min_width_mm,min_height_mm,max_length_mm,max_width_mm,max_height_mm)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        id_int,
                        name,
                        new_code,
                        old_code,
                        replacement_code,
                        max_weight_g,
                        min_length_mm,
                        min_width_mm,
                        min_height_mm,
                        max_length_mm,
                        max_width_mm,
                        max_height_mm,
                    ),
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute(f"DELETE FROM {self.repo.table_name} WHERE id = ?", (int(row_id),))
            cur.execute(f"UPDATE {self.repo.table_name} SET id = id - 1 WHERE id > ?", (int(row_id),))
            con.commit()

class _ReturnAddressesBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: ReturnAddressesRepository, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search contact/address/town/county/postcode...",
            headers=["ID", "Contact Name", "Address 1", "Address 2", "Address 3", "Town", "County", "Postcode"],
            query_error_title="Query return addresses",
            stretch_last_section=True,
            export_name="Return Addresses",
            parent=parent,
        )

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [
            row.get("ID", 0),
            row.get("contact_name", ""),
            row.get("address1", ""),
            row.get("address2", ""),
            row.get("address3", ""),
            row.get("Town", ""),
            row.get("County", ""),
            row.get("postcode", ""),
        ]

    def _extract_payload(self, r: int):
        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
            _get_cell_text(self.table, r, 4),
            _get_cell_text(self.table, r, 5),
            _get_cell_text(self.table, r, 6),
            _get_cell_text(self.table, r, 7),
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for row in payloads:
                cur.execute(
                    "INSERT INTO return_addresses (ID, contact_name, address1, address2, address3, Town, County, postcode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM return_addresses WHERE ID = ?", (int(row_id),))
            cur.execute("UPDATE return_addresses SET ID = ID - 1 WHERE ID > ?", (int(row_id),))
            con.commit()

class _UcidsBrowserTab(_BaseBrowserTab):
    def __init__(self, *, repo: UcidsRepository, parent=None):
        super().__init__(
            repo=repo,
            placeholder_text="Search poster/client/ucid...",
            headers=["ID", "Poster", "Client", "UCID 1", "UCID 2"],
            query_error_title="Query UCIDs",
            stretch_last_section=False,
            export_name="UCIDs",
            parent=parent,
        )
        self._apply_column_layout()

    def _apply_column_layout(self):
        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 60)

    def _set_rows(self, rows: list[dict]):
        super()._set_rows(rows)
        self._apply_column_layout()

    def _add_row(self):
        try:
            db_next_id = self._next_id()
        except Exception as e:
            QMessageBox.critical(self, "Add row", f"Could not determine next ID:\n{e}")
            return

        next_id = db_next_id

        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if not item:
                continue
            try:
                row_id = int(item.data(Qt.ItemDataRole.DisplayRole))
                if row_id >= next_id:
                    next_id = row_id + 1
            except Exception:
                continue

        self.table.setSortingEnabled(False)

        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, _make_readonly_id_item(next_id))

        for c in range(1, len(self._headers)):
            self.table.setItem(r, c, _make_editable_item(""))

        self._new_row_indices.append(r)
        self.table.setCurrentCell(r, 1)
        self.table.editItem(self.table.item(r, 1))

        self._apply_column_layout()

    def _list_all_rows(self) -> list[dict]:
        return self.repo.list_all()

    def _search_rows(self, q: str) -> list[dict]:
        return self.repo.search(q)

    def _next_id(self) -> int:
        return self.repo.next_id()

    def _row_to_display_values(self, row: dict) -> list:
        return [
            row.get("id", 0),
            row.get("poster", ""),
            row.get("client", ""),
            row.get("ucid1", ""),
            row.get("ucid2", ""),
        ]

    def _extract_payload(self, r: int):
        return (
            self._row_id_from_table(r),
            _get_cell_text(self.table, r, 1),
            _get_cell_text(self.table, r, 2),
            _get_cell_text(self.table, r, 3),
            _get_cell_text(self.table, r, 4),
        )

    def _insert_payloads(self, payloads: list):
        with self.repo._connect() as con:
            cur = con.cursor()
            for row in payloads:
                cur.execute(
                    f"""
                    INSERT INTO {self.repo.table_name} (id, poster, client, ucid1, ucid2)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    row,
                )
            con.commit()

    def _delete_row_by_id(self, row_id: int):
        with self.repo._connect() as con:
            cur = con.cursor()
            cur.execute(f"DELETE FROM {self.repo.table_name} WHERE id = ?", (int(row_id),))
            cur.execute(f"UPDATE {self.repo.table_name} SET id = id - 1 WHERE id > ?", (int(row_id),))
            con.commit()