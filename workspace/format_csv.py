from __future__ import annotations

from config.schemas.edit_csv_format import EDIT_CSV_FORMAT_SCHEMA
from workspace.base import BaseWorkflow


class FormatCSV(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT file to load",
            "CSV/TXT Files (*.csv *.txt);;All Files (*)"
        )
        if not infile:
            return

        opts = self.options_dialog(
            EDIT_CSV_FORMAT_SCHEMA,
            title="Edit CSV Format"
        )
        if not opts:
            return

        out_delim = opts.get("delimiter")
        if not out_delim:
            return

        header_mode = opts.get("header_cleaning", "none")  # none | underscore | dot

        def on_loaded(df, has_header: bool):
            # Header cleaning happens inside loader; no further action needed here.
            # Save back to same file (in-place)
            outfile = infile

            self.save_csv_then(
                df,
                outfile,
                title="Edit CSV Format",
                delimiter=out_delim,
                has_header=has_header,
                success_msg="File updated successfully.",
                sanitize=False,
            )

        self.load_df_then(
            infile,
            title="Edit CSV Format",
            header_mode=header_mode,   # <-- THIS is the key change
            make_writable=True,
            on_loaded=on_loaded
        )