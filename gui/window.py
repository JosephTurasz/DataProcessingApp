import os
import stat

from config.constants import APP_TITLE, CANCELLED_MSG, MAIN_WINDOW_MIN_HEIGHT, MAIN_WINDOW_MIN_WIDTH

from PySide6.QtWidgets import (QWidget,QVBoxLayout,QPushButton,QMessageBox,QLabel,QFileDialog,QGroupBox,QTextEdit)
from PySide6.QtCore import Qt, Signal

from workspace.services import build_services
from workspace.jobs import JobRunner

from workspace.format_csv import FormatCSV
from workspace.create_file import CreateFile
from workspace.split_file import SplitFile
from workspace.create_ecommerce_file import CreateEcommerceFile
from workspace.update_out_file import UpdateOutFile
from workspace.create_zip import CreateZip
from workspace.generate_password import GeneratePassword
from workspace.print_pdf import PrintPdf
from workspace.create_presorted_brief import CreatePresortedBrief
from workspace.move_items_to_folders import MoveItemsToFolders

from gui.dialogs.databases_dialog import QueryDatabasesDialog

class MainWindow(QWidget):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel("<h2>Data processing application.</h2>")
        header.setAlignment(Qt.AlignCenter)
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        group = QGroupBox("Processing Actions")
        group_layout = QVBoxLayout(group)
        layout.addWidget(group)
        # ---- Log ----
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.log_signal.connect(self.log.append)
        # ---- Services + Jobs ----
        self.s = build_services(self)
        self.jobs = JobRunner(self)
        # ---- Workflows ----
        self.format_csv = FormatCSV(self)
        self.create_file = CreateFile(self)
        self.split_file = SplitFile(self)
        self.create_ecommerce_file = CreateEcommerceFile(self)
        self.update_out_file = UpdateOutFile(self)
        self.create_zip = CreateZip(self)
        self.generate_password = GeneratePassword(self)
        self.print_pdf = PrintPdf(self)
        self.create_presorted_brief = CreatePresortedBrief(self)
        self.move_items_to_folders = MoveItemsToFolders(self)
        # ---- Actions (buttons + wiring) ----
        actions = [
            ("btn_query_databases", "Databases", lambda: QueryDatabasesDialog(self).exec()),
            ("btn_format_csv", "Edit CSV Format", self.format_csv.run),
            ("btn_move_items_to_folders", "Move items to folders", self.move_items_to_folders.run),
            ("btn_create_presorted_brief", "Create Pre-sorted Brief", self.create_presorted_brief.run),
            ("btn_create_file", "Create Mailing File", self.create_file.run),
            ("btn_split_file", "Split Mailing File", self.split_file.run),
            ("btn_create_ecommerce_file", "Create E-Commerce File", self.create_ecommerce_file.run),
            ("btn_update_out_file", "Update .OUT file", self.update_out_file.run),
            ("btn_create_zip", "Create ZIP", self.create_zip.run),
            ("btn_generate_random_password", "Generate Random Password", self.generate_password.run),
            ("btn_print_pdf", "Print PDF", self.print_pdf.run)]

        self._action_buttons: list[QPushButton] = []
        for attr, text, slot in actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.clicked.connect(slot)
            setattr(self, attr, btn)
            group_layout.addWidget(btn)
            self._action_buttons.append(btn)

        self.last_input_dir = os.getcwd()
    # ---------------- UI helpers ----------------
    def set_actions_enabled(self, enabled: bool) -> None:
        for b in getattr(self, "_action_buttons", []):
            try:
                b.setEnabled(bool(enabled))
            except Exception:
                pass

    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)
        self.s.logger.log(f"[ERROR] {title}: {text}", "red")

    def _get_start_dir(self, path=None):
        if path and os.path.exists(path):
            return path
        return self.last_input_dir or os.getcwd()

    def update_last_input_dir(self, selected_path):
        if not selected_path:
            return
        if isinstance(selected_path, (list, tuple)):
            selected_path = selected_path[0]
        if os.path.isfile(selected_path):
            self.last_input_dir = os.path.dirname(selected_path)
        elif os.path.isdir(selected_path):
            self.last_input_dir = selected_path

    def ask_open_file(self, title="Open file", filter="All Files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, title, self._get_start_dir(), filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def ask_open_files(self, title="Open files", filter="All Files (*)"):
        paths, _ = QFileDialog.getOpenFileNames(self, title, self._get_start_dir(), filter)
        if paths:
            self.update_last_input_dir(paths)
        return paths or None

    def ask_save_csv(self, title="Save file", filter="CSV Files (*.csv);;All Files (*)", defaultName=None):
        start_dir = self._get_start_dir()
        start_path = os.path.join(start_dir, defaultName) if defaultName else start_dir
        path, _ = QFileDialog.getSaveFileName(self, title, start_path, filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def make_file_writable(self, path: str):
        if os.path.exists(path):
            attrs = os.stat(path).st_mode
            if not (attrs & stat.S_IWRITE):
                os.chmod(path, attrs | stat.S_IWRITE)

    def _save_csv(self, df, filename, has_header=True, delimiter=","):
        def _chunk_fits_cp1252(text: str) -> bool:
            try:
                text.encode("cp1252", errors="strict")
                return True
            except UnicodeEncodeError:
                return False

        needs_utf8 = False
        if has_header and not _chunk_fits_cp1252("\n".join(str(c) for c in df.columns)):
            needs_utf8 = True

        if not needs_utf8:
            for col in df.columns:
                joined = "\n".join(df[col].astype(str).tolist())
                if not _chunk_fits_cp1252(joined):
                    needs_utf8 = True
                    break

        encoding = "utf-8" if needs_utf8 else "cp1252"
        label = "UTF-8" if needs_utf8 else "ANSI (cp1252)"

        df.to_csv(
            filename,
            index=False,
            header=has_header,
            sep=delimiter,
            encoding=encoding)
        return label

    def _run_busy(self,title: str,message: str,fn,on_done=None,on_err=None,cancelable: bool = False,progress_total=None):
        self.set_actions_enabled(False)
        cancelled = {"flag": False}

        def done_wrapper(res):
            self.set_actions_enabled(True)
            if cancelled["flag"]:
                return
            if on_done:
                on_done(res)

        def err_wrapper(err_text: str):
            self.set_actions_enabled(True)
            if (err_text or "").strip() == CANCELLED_MSG:
                return
            if on_err:
                on_err(err_text)
            else:
                self.show_error(title, err_text)

        job = self.jobs.run(title,message,fn,on_done=done_wrapper,on_err=err_wrapper,cancelable=cancelable,progress_total=progress_total,)

        try:
            def _mark_cancelled():
                cancelled["flag"] = True
                self.s.logger.log("User Interrupt", "yellow")

            job.cancel_requested.connect(_mark_cancelled)
        except Exception:
            pass

        return job