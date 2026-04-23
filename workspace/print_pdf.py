from __future__ import annotations

import os

from PySide6.QtWidgets import QDialog, QMessageBox

from config.constants import SYSTEM_PRINTERS
from config.schemas.print_pdf import PRINT_PDF_SCHEMA
from gui.dialogs.options_dialog import OptionsDialog
from gui.dialogs.printing_dialog import BatchPdfPrintDialog
from processing.pdf_labels import append_label
from utils.print_utils import move_pdf_to_folder, print_to_specific_printer


class PrintPdf:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        pdfs = self.mw.ask_open_files("Select PDFs for batch print", "PDF Files (*.pdf)")
        if not pdfs:
            return

        dlg_opts = OptionsDialog(PRINT_PDF_SCHEMA, parent=self.mw, title="Print Options")
        if dlg_opts.exec() != QDialog.Accepted:
            return
        print_opts = dlg_opts.get_results() or {}

        printed_dir = os.path.join(os.path.dirname(pdfs[0]), "Printed")

        dlg = BatchPdfPrintDialog(pdfs, parent=self.mw)

        def do_skip():
            dlg.skip_batch()
            if dlg.is_finished():
                dlg.accept()

        def do_print_current_batch():
            batch_files = dlg.current_batch_files()
            if not batch_files:
                dlg.accept()
                return

            dlg.set_controls_enabled(False)

            total = min(len(batch_files), len(SYSTEM_PRINTERS))
            enabled_label = bool(print_opts.get("print_filename_label", True))

            def job_print(progress):
                for idx, pdf in enumerate(batch_files[:total], start=1):
                    printer = SYSTEM_PRINTERS[idx - 1]
                    name = os.path.basename(pdf)

                    progress(idx - 1, total, f"Printing {idx}/{total}: {name} → {printer}")

                    final_pdf = append_label(pdf, enabled_label)
                    moved_to = None

                    try:
                        print_to_specific_printer(final_pdf, printer)
                        moved_to = move_pdf_to_folder(pdf, printed_dir)
                    finally:
                        if final_pdf and final_pdf != pdf:
                            try:
                                os.remove(final_pdf)
                            except Exception:
                                pass

                    if moved_to:
                        progress(
                            idx,
                            total,
                            f"Sent {idx}/{total}: {name} → {printer} | moved to {os.path.basename(moved_to)}",
                        )
                    else:
                        progress(idx, total, f"Sent {idx}/{total}: {name} → {printer}")

                return True

            def on_done(_res):
                dlg.set_controls_enabled(True)
                dlg.advance_batch()
                if dlg.is_finished():
                    dlg.accept()

            def on_err(err_text: str):
                dlg.set_controls_enabled(True)
                QMessageBox.critical(dlg, "Print Error", err_text)

            self.mw._run_busy(
                "Printing PDFs",
                f"Sending 0/{total}…",
                job_print,
                on_done=on_done,
                on_err=on_err,
                cancelable=False,
                progress_total=total,
            )

        dlg.skip_requested.connect(do_skip)
        dlg.print_requested.connect(do_print_current_batch)

        dlg.exec()