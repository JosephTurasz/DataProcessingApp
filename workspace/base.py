from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import pandas as pd

from config.constants import SELECT_PLACEHOLDER, SENTINEL_NONE, SENTINEL_SELECT

from PySide6.QtWidgets import QDialog, QMessageBox

from gui.dialogs.options_dialog import OptionsDialog
from gui.dialogs.preview_dialog import PreviewDialog

DoneHandler = Callable[[Any], None]
ErrHandler = Callable[[str], None]

@dataclass
class BaseWorkflow:
    mw: Any
    # ---------------- Messaging ----------------
    def info(self, msg: str, colour: str = "green") -> None:
        self.mw.s.logger.log(msg, colour)

    def warn(self, title: str, msg: str) -> None:
        QMessageBox.warning(self.mw, title, msg)

    def fail(self, title: str, err_text: str) -> None:
        self.mw.show_error(title, (err_text or "").strip() or "Unknown error")

    def fail_exception(self, title: str, exc: Exception) -> None:
        self.fail(title, str(exc))
    # ---------------- Busy job wrappers ----------------
    def busy(
        self,
        title: str,
        message: str,
        fn: Callable[[], Any],
        *,
        on_done: Optional[DoneHandler] = None,
        on_err: Optional[ErrHandler] = None,
        cancelable: bool = False):
        return self.mw._run_busy(title,message,fn,on_done=on_done,on_err=on_err or (lambda e: self.fail(title, e)),cancelable=cancelable)
    # ---------------- helpers ----------------
    def options_dialog(self, schema, *, title: str) -> Optional[dict]:
        dlg = OptionsDialog(schema, parent=self.mw, title=title)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_results()

    def preview_dialog(self, df, *, title: str = "Preview"):
        dlg = PreviewDialog(df, self.mw, title=title)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_dataframe()
    
    def sanitize_df_for_export(self, df):
        return df.map(lambda x: str(x).replace("\n", " ").strip())
    
    def drop_empty_rows_cols(self, df):
        if df is None or df.empty:
            return df
        tmp = df.astype(object).where(pd.notnull(df), "")
        non_empty = tmp.astype(str).apply(lambda s: s.str.strip().ne(""))

        keep_rows = non_empty.any(axis=1)

        # Only drop columns that are fully empty AND have no meaningful header.
        # A column with a real header but all-blank data must be preserved.
        col_has_data = non_empty.any(axis=0)
        col_has_real_header = pd.Series(
            [
                bool(str(c).strip()) and not re.fullmatch(r"Column\d+", str(c).strip())
                for c in df.columns
            ],
            index=df.columns,
        )
        keep_cols = col_has_data | col_has_real_header

        out = df.loc[keep_rows, keep_cols].copy()
        out.reset_index(drop=True, inplace=True)
        return out
    
    def ask_save_csv_default_from_infile(self,infile: str,*,title: str,suffix: str = ".csv",filter: str = "CSV Files (*.csv);;All Files (*)") -> Optional[str]:
        import os
        base = os.path.splitext(os.path.basename(infile))[0]
        default_name = f"{base}{suffix}"
        return self.mw.ask_save_csv(title, filter, defaultName=default_name)
    # ---------------- Common workflow phases ----------------
    def load_df_then(self,infile: str,*,title: str,header_mode: str = "none",make_writable: bool = False,on_loaded: Callable[[Any, bool], None]):
        if make_writable:
            try:
                self.mw.make_file_writable(infile)
            except Exception:
                pass

        def job_load(_progress, cancel):
            return self.mw.s.loader.load_file(infile,header_cleaning_mode=header_mode,cancel_event=cancel,)

        def handle_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return
                on_loaded(df, bool(has_header))
            except Exception as e:
                self.fail_exception(f"{title} failed", e)
        return self.busy(title,"Loading file…",job_load,on_done=handle_loaded,cancelable=True,)

    def save_csv_then(self,df,outfile: str,*,title: str,delimiter: str,has_header: bool,success_msg: str = "File created successfully.",sanitize: bool = True):
        if sanitize:
            df = self.sanitize_df_for_export(df)

        def job_save():
            enc_label = self.mw._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
            return enc_label

        def done(enc_label):
            suffix = f' (Encoding: {enc_label})' if enc_label else ""
            self.info(f"{success_msg}{suffix}", "green")

        return self.busy(title,"Saving file…",job_save,on_done=done,on_err=lambda e: QMessageBox.critical(self.mw, "Save Error", e),)

    def run_busy(self,title: str,message: str,fn: Callable[[], Any],*,success_msg: Optional[str] = None,on_done: Optional[DoneHandler] = None,
                 on_err: Optional[ErrHandler] = None,cancelable: bool = False):
        if on_done is None and success_msg is not None:
            on_done = lambda _res: self.info(success_msg, "green")
        return self.busy(title, message, fn, on_done=on_done, on_err=on_err, cancelable=cancelable)
    # ---------------- UCID helpers ----------------
    def _selected_ucid_row(self, opts: dict) -> dict | None:
        poster = str(opts.get("ucid_poster", "") or "").strip()
        client = str(opts.get("ucid_client", "") or "").strip()

        if poster == SENTINEL_SELECT:
            poster = ""
        if client == SENTINEL_SELECT:
            client = ""

        if not poster or not client:
            return None

        return self.mw.s.ucids_repo.get_by_client_poster(client=client, poster=poster)

    def _filter_seed_rows_for_available_ucids(self, rows_to_add: list[list[str]], opts: dict) -> list[list[str]]:
        row = self._selected_ucid_row(opts)
        if not row:
            return rows_to_add

        ucid1 = str(row.get("ucid1", "") or "").strip()
        ucid2 = str(row.get("ucid2", "") or "").strip()

        has_ucid1 = bool(ucid1)
        has_ucid2 = bool(ucid2)

        if has_ucid1 and has_ucid2:
            return rows_to_add

        filtered: list[list[str]] = []
        for seed_row in rows_to_add:
            values = [str(v or "").strip().upper() for v in seed_row]
            mentions_ucid2 = any("UCID2" in v for v in values)

            # If only one UCID exists, drop any seed row that references UCID2
            if (has_ucid1 ^ has_ucid2) and mentions_ucid2:
                continue

            filtered.append(seed_row)

        return filtered

    def _apply_seed_ucids_if_needed(self, df, opts: dict):
        try:
            row = self._selected_ucid_row(opts)
            if not row:
                self.mw.s.logger.log("[UCID] No UCIDs inserted - Update the outfile", "yellow")
                return df

            ucid1 = str(row.get("ucid1", "") or "").strip()
            ucid2 = str(row.get("ucid2", "") or "").strip()

            if ucid1 and ucid2:
                self.mw.s.transforms.update_UCID(df, {"UCID1": ucid1, "UCID2": ucid2})
                self.mw.s.logger.log(f"[UCID] Inserted UCIDs {ucid1} and {ucid2} successfully", "green")
                return df

            single_ucid = ucid1 or ucid2
            if single_ucid:
                self.mw.s.transforms.update_UCID(df, {"UCID1": single_ucid, "UCID2": single_ucid})
                self.mw.s.logger.log(f"[UCID] Inserted UCID {single_ucid} successfully, single seed added", "yellow")
                return df

            self.mw.s.logger.log("[UCID] No UCIDs inserted - Update the outfile", "yellow")
            return df

        except Exception as e:
            self.mw.s.logger.log(f"[UCID] UCID Error - {e}", "red")
            return df