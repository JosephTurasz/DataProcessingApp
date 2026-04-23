from __future__ import annotations

from config.constants import SELECT_PLACEHOLDER, SENTINEL_SELECT
from config.schemas.update_out_file import build_update_out_file_schema
from workspace.base import BaseWorkflow


class UpdateOutFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT to update",
            "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)",
        )
        if not infile:
            return

        poster_options = [SELECT_PLACEHOLDER] + self.mw.s.ucids_repo.list_poster_options()
        client_options = [SELECT_PLACEHOLDER] + self.mw.s.ucids_repo.list_client_options()

        opts = self.options_dialog(
            build_update_out_file_schema(
                poster_options=poster_options,
                client_options=client_options,
            ),
            title="Update Out File",
        )
        if not opts:
            return

        def _resolve_switch_value(opts: dict, key_prefix: str) -> str:
            mode = str(opts.get(f"{key_prefix}_mode", "a") or "a").strip()

            if mode == "b":
                return str(opts.get(f"{key_prefix}_text", "") or "").strip()

            value = str(opts.get(f"{key_prefix}_select", "") or "").strip()
            return "" if value == SENTINEL_SELECT else value

        poster = _resolve_switch_value(opts, "poster")
        client = _resolve_switch_value(opts, "client")

        existing_ucid_record = None
        if poster and client:
            existing_ucid_record = self.mw.s.ucids_repo.get_by_client_poster(client=client, poster=poster)
            if existing_ucid_record:
                if not str(opts.get("ucid1", "") or "").strip():
                    opts["ucid1"] = str(existing_ucid_record.get("ucid1", "") or "").strip()
                if not str(opts.get("ucid2", "") or "").strip():
                    opts["ucid2"] = str(existing_ucid_record.get("ucid2", "") or "").strip()

        def on_loaded(df, has_header: bool):
            try:
                ucid_mode = str(opts.get("ucid_updates", "none") or "none").strip()

                ucid1 = str(opts.get("ucid1", "") or "").strip()
                ucid2 = str(opts.get("ucid2", "") or "").strip()

                ucid_map = {}

                if ucid_mode == "1":
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                        ucid_map["UCID2"] = ucid1

                elif ucid_mode == "2":
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                    if ucid2:
                        ucid_map["UCID2"] = ucid2

                if ucid_map:
                    self.mw.s.transforms.update_UCID(df, ucid_map)

                barcode_type = str(opts.get("barcode_type", "none") or "none")
                if barcode_type != "none":
                    df = self.mw.s.transforms.convert_barcode_type(df, int(barcode_type))

                padding_choice = str(opts.get("barcode_padding", "none") or "none")
                if padding_choice != "none":
                    df = self.mw.s.transforms.apply_barcode_padding(df, padding_choice)

                delimiter = self.mw.s.loader.last_delimiter

                self.save_csv_then(
                    df,
                    infile,
                    title="Update OUT File",
                    delimiter=delimiter,
                    has_header=has_header,
                    success_msg="OUT file updated successfully.",
                    sanitize=False,
                )

                if ucid_mode != "none" and poster and client and existing_ucid_record is None:
                    self.mw.s.ucids_repo.upsert_client_poster_ucids(
                        client=client,
                        poster=poster,
                        ucid1=ucid1,
                        ucid2=ucid2,
                    )

            except Exception as e:
                self.fail_exception("Update OUT file failed", e)
                
        self.load_df_then(
            infile,
            title="Update OUT File",
            make_writable=True,
            on_loaded=on_loaded,
        )