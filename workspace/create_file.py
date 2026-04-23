from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from config.constants import SELECT_PLACEHOLDER, SENTINEL_NONE, SENTINEL_SELECT
from config.schemas.create_file import build_create_file_schema
from workspace.base import BaseWorkflow


class CreateFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        standard_options = self.mw.s.seeds_repo.list_seed_options("Standard")
        bespoke_options = self.mw.s.seeds_repo.list_seed_options("Bespoke")
        poster_options = [SELECT_PLACEHOLDER] + self.mw.s.ucids_repo.list_poster_options()

        def client_options_provider(poster_value):
            poster_value = str(poster_value or "").strip()
            if not poster_value or poster_value == SENTINEL_SELECT:
                return [SELECT_PLACEHOLDER]
            return [SELECT_PLACEHOLDER] + self.mw.s.ucids_repo.list_client_options(poster_value)

        schema = build_create_file_schema(
            standard_options=standard_options,
            bespoke_options=bespoke_options,
            poster_options=poster_options,
            client_options_provider=client_options_provider,
        )
        opts = self.options_dialog(schema, title="Create File Options")

        if not opts:
            return

        header_mode = opts.get("header_cleaning", "none")

        def on_loaded(df, has_header: bool):
            # -------------------- MMI --------------------
            mmi_opts = opts.get("mmi", {}) or {}
            if mmi_opts.get("enabled"):
                mmi_type = mmi_opts.get("value")
                try:
                    if mmi_type == "Scotts":
                        cell_name = (mmi_opts.get("cell_name") or "").strip()
                        if not cell_name:
                            self.warn("Missing cell name", "Scotts MMI requires a cell name.")
                            return
                        df_mmi = self.mw.s.transforms.append_mmi(df, "Scotts", cell_name=cell_name, logger=self.mw.s.logger)
                    else:
                        df_mmi = self.mw.s.transforms.append_mmi(df, mmi_type, logger=self.mw.s.logger)
                    df = df_mmi
                except Exception as e:
                    QMessageBox.critical(self.mw, "MMI Error", str(e))
                    return

            # -------------------- Seeds --------------------
            seed_opts = opts.get("seeds", {}) or {}
            if seed_opts.get("enabled"):
                std_id = seed_opts.get("standard_seed")
                bes_id = seed_opts.get("bespoke_seed")
                try:
                    rows_to_add = []
                    if std_id:
                        rows_to_add += self.mw.s.seeds_repo.get_seed_rows(std_id)

                    if bes_id and bes_id != SENTINEL_NONE:
                        rows_to_add += self.mw.s.seeds_repo.get_seed_rows(bes_id)

                    rows_to_add = self._filter_seed_rows_for_available_ucids(rows_to_add, opts)

                    ncols = len(df.columns)
                    if ncols == 5:
                        self.mw.s.logger.log("Append seeds: dropping DPS column", "yellow")
                    elif ncols == 4:
                        self.mw.s.logger.log("Append seeds: dropping Address 2 and DPS columns", "yellow")

                    if rows_to_add:
                        df = self.mw.s.transforms.append_seeds(df, rows_to_add)
                        df = self._apply_seed_ucids_if_needed(df, opts)
                except Exception as e:
                    msg = str(e).strip() or "Append seeds failed"
                    self.mw.s.logger.log(msg, "red")
                    return

            # -------------------- Preview/Edit --------------------
            edited = self.preview_dialog(df, title="Preview")
            if edited is None:
                return
            df = self.drop_empty_rows_cols(edited)

            # -------------------- Save --------------------
            delimiter = opts.get("delimiter", ",")
            outfile = self.ask_save_csv_default_from_infile(
                infile,
                title="Save output file",
                suffix=".csv",
                filter="CSV Files (*.csv);;All Files (*)",
            )
            if not outfile:
                return

            self.save_csv_then(
                df,
                outfile,
                title="Create File",
                delimiter=delimiter,
                has_header=has_header,
                success_msg="File created successfully.",
                sanitize=True,
            )

        self.load_df_then(
            infile,
            title="Create File",
            header_mode=header_mode,
            make_writable=False,
            on_loaded=on_loaded,
        )