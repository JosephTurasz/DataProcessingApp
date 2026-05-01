from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        error_dir = os.path.join(os.path.dirname(pdfs[0]), "Error")

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
                def print_one(idx: int, pdf: str) -> str | None:
                    printer = SYSTEM_PRINTERS[idx - 1]
                    final_pdf = append_label(pdf, enabled_label)
                    try:
                        print_to_specific_printer(final_pdf, printer)
                        move_pdf_to_folder(pdf, printed_dir)
                        return None
                    except Exception as exc:
                        try:
                            move_pdf_to_folder(pdf, error_dir)
                        except Exception:
                            pass
                        return f"{os.path.basename(pdf)} → {printer}: {exc}"
                    finally:
                        if final_pdf and final_pdf != pdf:
                            try:
                                os.remove(final_pdf)
                            except Exception:
                                pass

                progress(0, 0, f"Spooling {total} print job(s)…")

                job_errors: list[str] = []
                with ThreadPoolExecutor(max_workers=total) as pool:
                    futures = [
                        pool.submit(print_one, idx, pdf)
                        for idx, pdf in enumerate(batch_files[:total], start=1)
                    ]
                    for fut in as_completed(futures):
                        err = fut.result()
                        if err:
                            job_errors.append(err)

                return job_errors

            def on_done(job_errors: list[str]):
                dlg.set_controls_enabled(True)
                if job_errors:
                    err_list = "\n".join(f"  • {e}" for e in job_errors)
                    QMessageBox.warning(
                        dlg,
                        "Print Errors",
                        f"The following job(s) failed and were moved to the Error folder:\n\n{err_list}",
                    )
                dlg.advance_batch()
                if dlg.is_finished():
                    dlg.accept()

            def on_err(err_text: str):
                dlg.set_controls_enabled(True)
                QMessageBox.critical(dlg, "Print Error", err_text)

            self.mw._run_busy(
                "Printing PDFs",
                f"Spooling {total} print job(s)…",
                job_print,
                on_done=on_done,
                on_err=on_err,
                cancelable=False,
            )

        dlg.skip_requested.connect(do_skip)
        dlg.print_requested.connect(do_print_current_batch)

        dlg.exec()