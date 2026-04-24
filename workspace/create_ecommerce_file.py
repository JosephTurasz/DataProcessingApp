from __future__ import annotations

import os
from typing import Any

import pandas as pd
from PySide6.QtWidgets import QDialog

from processing.ecommerce.defaults import EcommerceDefaults
from processing.ecommerce.mapping import EcommerceMapping
from processing.ecommerce.paf_resolution import EcommercePafResolution
from processing.ecommerce.services import EcommerceServices
from processing.ecommerce.transforms import EcommerceTransforms
from workspace.base import BaseWorkflow

from config.schemas.create_ecommerce_file import build_create_ecommerce_file_schema
from config.constants import FIELD_LENGTH_COLUMNS, FIELD_LENGTH_LIMIT, SELECT_PLACEHOLDER, SENTINEL_SELECT

from gui.dialogs.options_dialog import OptionsDialog
from gui.dialogs.paf_resolution_dialog import PAFResolutionDialog
from gui.dialogs.recipient_name_resolution_dialog import RecipientNameResolutionDialog
from gui.dialogs.service_resolution_dialog import ServiceResolutionDialog
from gui.dialogs.field_length_resolution_dialog import FieldLengthResolutionDialog


def _validate_info_field(
    workflow: BaseWorkflow,
    *,
    df: pd.DataFrame,
    mode: str | None,
    source_column: str | None,
    text_value: str | None,
    field_label: str,
) -> bool:
    if mode == "a":
        if (
            not source_column
            or source_column == SENTINEL_SELECT
            or source_column not in df.columns
        ):
            workflow.warn("Create E-Commerce File", f"Please select a {field_label.lower()} column.")
            return False

    elif mode == "b":
        if not str(text_value or "").strip():
            workflow.warn("Create E-Commerce File", f"Please enter a {field_label.lower()} value.")
            return False

    return True


class CreateEcommerceFile(BaseWorkflow):
    RECIPIENT_FIELD_SPECS = [
        {"prefix": "name", "label": "Name", "required": True},
        {"prefix": "surname", "label": "Surname", "required": False},
    ]

    INFO_FIELD_SPECS = [
        {"prefix": "company", "label": "Company", "output": "Company", "required": False},
        {"prefix": "reference", "label": "Reference", "output": "Client Item Reference", "required": True},
        {"prefix": "service", "label": "Service", "output": "Service", "required": True},
        {"prefix": "weight", "label": "Weight", "output": "Weight", "required": True},
        {"prefix": "length", "label": "Length", "output": "Length", "required": True},
        {"prefix": "width", "label": "Width", "output": "Width", "required": True},
        {"prefix": "height", "label": "Height", "output": "Height", "required": True},
        {"prefix": "country_code", "label": "Country Code", "output": "Country Code", "required": False},
        {"prefix": "quantity", "label": "Quantity", "output": "Quantity", "required": False},
        {"prefix": "product_description", "label": "Product Description", "output": "Product Description", "required": False},
        {"prefix": "retail_value", "label": "Retail Value", "output": "Retail Value", "required": False},
    ]

    def __init__(self, mw):
        super().__init__(mw)
        self.defaults = EcommerceDefaults()
        self.mapping = EcommerceMapping()
        self.transforms = EcommerceTransforms()
        self.service_rules = EcommerceServices()
        self.paf_resolution = EcommercePafResolution(self.transforms)

    def run(self, checked: bool = False):
        self.service_rules._rule_maps_cache = None
        self.transforms._return_address_cache = {}

        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        def on_loaded(df: pd.DataFrame, has_header: bool):
            if df is None or df.empty:
                self.warn("Create E-Commerce File", "File contains no data.")
                return

            opts = self._prompt_for_options(df)
            if opts is None:
                return

            if not self._validate_core_options(df, opts):
                return

            fields = self._collect_fields(opts)
            multiply_weight_by_quantity = bool(opts.get("multiply_weight_by_quantity", False))
            change_service_code = bool(opts.get("change_service_code", True))
            use_max_service_dimensions = bool(opts.get("use_max_service_dimensions", False))
            use_windsor_agreement_defaults = bool(opts.get("use_windsor_agreement_defaults", False))
            export_in_batches_of_300 = bool(opts.get("export_in_batches_of_300", False))
            selected_return_address = opts.get("return_address")

            if not self._validate_selected_fields(
                df,
                fields=fields,
                use_max_service_dimensions=use_max_service_dimensions,
                use_windsor_agreement_defaults=use_windsor_agreement_defaults,
            ):
                return

            postcode_col = str(opts["postcode_column"])
            town_col = str(opts["town_column"])
            county_col = opts.get("county_column")
            address_start = opts.get("address_start")
            address_end = opts.get("address_end")
            out_delim = (opts.get("delimiter") or ",").strip() or ","

            try:
                preview_columns = self.mapping.build_preview_columns(
                    all_columns=list(df.columns),
                    address_start=address_start,
                    address_end=address_end,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
            except ValueError as e:
                self.warn("Create E-Commerce File", str(e))
                return

            preview_specs = self.mapping.build_preview_specs(
                preview_columns=preview_columns,
                town_col=town_col,
                county_col=county_col,
                postcode_col=postcode_col,
            )

            prepared_df = self.transforms.populate_missing_town_from_county_or_address(
                df,
                town_col=town_col,
                county_col=county_col,
                postcode_col=postcode_col,
                preview_columns=preview_columns,
            )

            paf_loop_result = self._run_paf_resolution_loop(
                prepared_df,
                postcode_col=postcode_col,
                town_col=town_col,
                preview_specs=preview_specs,
            )
            if paf_loop_result is None:
                return

            resolved_df, paf_reject_df = paf_loop_result

            def job_build():
                return self._build_pre_service_frames(
                    prepared_df=resolved_df,
                    fields=fields,
                    multiply_weight_by_quantity=multiply_weight_by_quantity,
                    change_service_code=change_service_code,
                    use_max_service_dimensions=use_max_service_dimensions,
                    use_windsor_agreement_defaults=use_windsor_agreement_defaults,
                    selected_return_address=selected_return_address,
                    paf_reject_df=paf_reject_df,
                )

            def on_done(build_result):
                if build_result is None:
                    return

                working_df, paf_reject_df_local = build_result

                working_df, recipient_reject_df = self._run_recipient_name_resolution_loop(
                    working_df,
                    preview_specs=preview_specs,
                )

                # Rename address columns to PAF names before service/field-length
                # resolution so PAF Address / PAF Town / PAF County are visible
                # to the field length check (they are in FIELD_LENGTH_COLUMNS).
                working_df = self.mapping.rename_to_paf_columns(
                    working_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )

                working_df = self._run_service_resolution_loop(
                    working_df,
                    use_max_service_dimensions=use_max_service_dimensions,
                )
                if working_df is None:
                    return

                working_df = self._run_field_length_resolution_warning(working_df)
                if working_df is None:
                    return

                working_df, service_reject_df = self.service_rules.split_valid_and_service_rejects(
                    working_df,
                    ecom_services_repo=self.mw.s.ecom_services_repo,
                )

                # working_df already has PAF column names — no further rename needed.
                valid_df = self.mapping.order_ecommerce_output_columns(working_df)

                paf_reject_df_local = self._rename_reject_frame_to_paf(
                    paf_reject_df_local,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                paf_reject_df_local = self.mapping.order_ecommerce_output_columns(paf_reject_df_local)

                recipient_reject_df = self._rename_reject_frame_to_paf(
                    recipient_reject_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                recipient_reject_df = self.mapping.order_ecommerce_output_columns(recipient_reject_df)

                service_reject_df = self._rename_reject_frame_to_paf(
                    service_reject_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                service_reject_df = self.mapping.order_ecommerce_output_columns(service_reject_df)

                reject_df = self.transforms.concat_frames(
                    [paf_reject_df_local, recipient_reject_df, service_reject_df]
                )
                if reject_df is not None and not reject_df.empty:
                    reject_df = self.mapping.order_ecommerce_output_columns(reject_df)

                edited = self.preview_dialog(valid_df, title="Preview (E-Commerce File)")
                if edited is None:
                    return

                edited = self.drop_empty_rows_cols(edited)

                outfile = self.ask_save_csv_default_from_infile(
                    infile,
                    title="Save E-Commerce output file",
                    suffix=" (ecommerce).csv",
                    filter="CSV Files (*.csv);;All Files (*)",
                )
                if not outfile:
                    return

                if export_in_batches_of_300:
                    self._save_output_in_batches(
                        edited,
                        outfile=outfile,
                        title="Create E-Commerce File",
                        delimiter=out_delim,
                        has_header=has_header,
                        batch_size=300,
                    )
                else:
                    self.save_csv_then(
                        edited,
                        outfile,
                        title="Create E-Commerce File",
                        delimiter=out_delim,
                        has_header=has_header,
                        success_msg="E-Commerce file created successfully.",
                        sanitize=True,
                    )

                if reject_df is not None and not reject_df.empty:
                    reject_path = outfile.replace(".csv", "_Rejects.csv")
                    reject_df = self.sanitize_df_for_export(reject_df)
                    self.mw._save_csv(reject_df, reject_path, has_header=True, delimiter=",")

            self.busy(
                "Create E-Commerce File",
                "Building E-Commerce file…",
                job_build,
                on_done=on_done,
                on_err=lambda e: self.fail("Create E-Commerce File", e),
                cancelable=True,
            )

        self.load_df_then(
            infile,
            title="Create E-Commerce File",
            header_mode="none",
            on_loaded=on_loaded,
        )

    def _prompt_for_options(self, df: pd.DataFrame) -> dict[str, Any] | None:
        from PySide6.QtCore import Qt, QEventLoop
        from PySide6.QtWidgets import QProgressDialog, QApplication

        cover = QProgressDialog("Preparing…", None, 0, 0, self.mw)
        cover.setWindowTitle("Create E-Commerce File")
        cover.setWindowModality(Qt.WindowModality.ApplicationModal)
        cover.setCancelButton(None)
        cover.setMinimumDuration(0)
        cover.show()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

        col_options = [SELECT_PLACEHOLDER]
        col_options += [(str(c), str(c)) for c in df.columns]

        return_address_options = [SELECT_PLACEHOLDER] + self.mw.s.return_addresses_repo.list_options()

        preview_rows = df.head(10).fillna("").to_dict("records")
        schema = build_create_ecommerce_file_schema(
            column_options=col_options,
            preview_rows=preview_rows,
            return_address_options=return_address_options,
        )

        detected_defaults = self.defaults.detect_ecommerce_defaults(list(df.columns))
        self.defaults.apply_schema_defaults(schema, detected_defaults)

        dlg = OptionsDialog(
            schema,
            parent=self.mw,
            title="Create E-Commerce File",
            initial_size=(1400, 900),
            minimum_size=(1320, 900),
            minimum_content_width=1200,
        )

        cover.close()
        cover.deleteLater()

        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_results()

    def _validate_core_options(self, df: pd.DataFrame, opts: dict[str, Any]) -> bool:
        postcode_col = opts.get("postcode_column")
        town_col = opts.get("town_column")
        county_col = opts.get("county_column")

        if not postcode_col or postcode_col == SENTINEL_SELECT or postcode_col not in df.columns:
            self.warn("Create E-Commerce File", "Please select a postcode column.")
            return False

        if not town_col or town_col == SENTINEL_SELECT or town_col not in df.columns:
            self.warn("Create E-Commerce File", "Please select a town column.")
            return False

        if county_col and county_col != SENTINEL_SELECT and county_col not in df.columns:
            self.warn("Create E-Commerce File", "Selected county column was not found.")
            return False

        return True

    def _read_switch_field(self, opts: dict[str, Any], prefix: str) -> dict[str, Any]:
        return {
            "mode": opts.get(f"{prefix}_mode"),
            "column": opts.get(f"{prefix}_column"),
            "text": opts.get(f"{prefix}_text"),
        }

    def _collect_fields(self, opts: dict[str, Any]) -> dict[str, dict[str, Any]]:
        fields: dict[str, dict[str, Any]] = {}

        for spec in self.RECIPIENT_FIELD_SPECS:
            field = self._read_switch_field(opts, spec["prefix"])
            field["label"] = spec["label"]
            field["required"] = spec["required"]
            fields[spec["prefix"]] = field

        for spec in self.INFO_FIELD_SPECS:
            field = self._read_switch_field(opts, spec["prefix"])
            field["label"] = spec["label"]
            field["required"] = spec["required"]
            field["output"] = spec["output"]
            fields[spec["prefix"]] = field

        return fields

    def _validate_selected_fields(
        self,
        df: pd.DataFrame,
        *,
        fields: dict[str, dict[str, Any]],
        use_max_service_dimensions: bool = False,
        use_windsor_agreement_defaults: bool = False,
    ) -> bool:
        for spec in self.RECIPIENT_FIELD_SPECS:
            field = fields[spec["prefix"]]
            if field["required"]:
                if not _validate_info_field(
                    self,
                    df=df,
                    mode=field.get("mode"),
                    source_column=field.get("column"),
                    text_value=field.get("text"),
                    field_label=field["label"],
                ):
                    return False

        windsor_locked_outputs = {"Country Code", "Retail Value", "Product Description", "Quantity"}

        for spec in self.INFO_FIELD_SPECS:
            field = fields[spec["prefix"]]

            if use_max_service_dimensions and field.get("output") in {"Length", "Width", "Height"}:
                continue

            if use_windsor_agreement_defaults and field.get("output") in windsor_locked_outputs:
                continue

            if field["required"]:
                if not _validate_info_field(
                    self,
                    df=df,
                    mode=field.get("mode"),
                    source_column=field.get("column"),
                    text_value=field.get("text"),
                    field_label=field["label"],
                ):
                    return False

        # Detect duplicate source columns — apply_info_field renames on first use,
        # so a second field pointing at the same source would silently get no data.
        seen_sources: dict[str, str] = {}
        for spec in self.INFO_FIELD_SPECS:
            field = fields[spec["prefix"]]
            if field.get("mode") == "a":
                src = field.get("column", "")
                if src and src not in (SENTINEL_SELECT, ""):
                    if src in seen_sources:
                        self.warn(
                            "Create E-Commerce File",
                            f"Column '{src}' is mapped to both '{seen_sources[src]}' and "
                            f"'{spec['output']}'. Each source column can only be used once.",
                        )
                        return False
                    seen_sources[src] = spec["output"]

        return True

    def _run_paf_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
        postcode_col: str,
        town_col: str,
    ) -> dict[str, Any] | None:
        if not resolution_state["resolution_postcodes"]:
            return {
                "corrected": {},
                "added": {},
                "removed": set(),
                "row_updates": {},
            }

        dialog = PAFResolutionDialog(
            current_postcodes=resolution_state["resolution_postcodes"],
            issue_labels=resolution_state["issue_labels"],
            row_previews=resolution_state["row_previews"],
            preview_specs=resolution_state["preview_specs"],
            postcode_column=postcode_col,
            town_column=town_col,
            normalizer=lambda x: self.transforms.collapse_postcode_series(pd.Series([x]))[0],
            parent=self.mw,
        )

        if not dialog.exec():
            return None

        result = dialog.result()
        return {
            "corrected": result["corrected"],
            "added": result["added"],
            "removed": result["removed"],
            "row_updates": result.get("row_updates", {}),
        }

    def _run_paf_resolution_loop(
        self,
        df: pd.DataFrame,
        *,
        postcode_col: str,
        town_col: str,
        preview_specs: list[dict[str, str]],
    ) -> tuple[pd.DataFrame, pd.DataFrame] | None:
        working_df = df.copy()
        all_paf_rejects: list[pd.DataFrame] = []

        while True:
            resolution_state = self.paf_resolution.collect_resolution_state(
                working_df,
                postcode_col=postcode_col,
                town_col=town_col,
                preview_specs=preview_specs,
                postcodes_repo=self.mw.s.postcodes_repo,
            )

            if not resolution_state["resolution_postcodes"]:
                reject_df = self.transforms.concat_frames(all_paf_rejects)
                return working_df, reject_df

            resolution_result = self._run_paf_resolution_dialog_if_needed(
                resolution_state=resolution_state,
                postcode_col=postcode_col,
                town_col=town_col,
            )
            if resolution_result is None:
                return None

            working_df, paf_reject_df = self.paf_resolution.apply_resolution_result(
                working_df,
                postcode_col=postcode_col,
                resolution_state=resolution_state,
                resolution_result=resolution_result,
                postcodes_repo=self.mw.s.postcodes_repo,
                logger=self.mw.s.logger,
            )

            if paf_reject_df is not None and not paf_reject_df.empty:
                all_paf_rejects.append(paf_reject_df)

    def _apply_all_info_fields(
        self,
        frame: pd.DataFrame,
        *,
        fields: dict[str, dict[str, Any]],
        multiply_weight_by_quantity: bool,
        change_service_code: bool,
        use_windsor_agreement_defaults: bool = False,
    ) -> pd.DataFrame:
        out = frame.copy()

        # Apply Company first so Recipient Name can fall back to it when blank.
        company_field = fields["company"]
        out = self.transforms.apply_info_field(
            out,
            mode=company_field.get("mode"),
            source_column=company_field.get("column"),
            text_value=company_field.get("text"),
            output_column="Company",
        )

        out = self.transforms.apply_recipient_name(
            out,
            name_mode=fields["name"].get("mode"),
            name_column=fields["name"].get("column"),
            name_text=fields["name"].get("text"),
            surname_mode=fields["surname"].get("mode"),
            surname_column=fields["surname"].get("column"),
            surname_text=fields["surname"].get("text"),
        )

        for spec in self.INFO_FIELD_SPECS:
            if spec["prefix"] == "company":
                continue

            field = fields[spec["prefix"]]
            out = self.transforms.apply_info_field(
                out,
                mode=field.get("mode"),
                source_column=field.get("column"),
                text_value=field.get("text"),
                output_column=spec["output"],
            )

        if use_windsor_agreement_defaults:
            out = self.service_rules.apply_default_windsor_details(out)

        if change_service_code:
            out = self.service_rules.use_replacement_service_code(
                out,
                ecom_services_repo=self.mw.s.ecom_services_repo,
                service_column="Service",
            )

        if multiply_weight_by_quantity:
            out = self.transforms.multiply_weight_by_quantity(out)

        return out

    def _build_pre_service_frames(
        self,
        *,
        prepared_df: pd.DataFrame,
        fields: dict[str, dict[str, Any]],
        multiply_weight_by_quantity: bool,
        change_service_code: bool,
        use_max_service_dimensions: bool,
        use_windsor_agreement_defaults: bool,
        selected_return_address: str | None,
        paf_reject_df: pd.DataFrame | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        working_df = prepared_df.copy()

        working_df = self._apply_all_info_fields(
            working_df,
            fields=fields,
            multiply_weight_by_quantity=multiply_weight_by_quantity,
            change_service_code=change_service_code,
            use_windsor_agreement_defaults=use_windsor_agreement_defaults,
        )

        working_df = self.transforms.apply_return_address(
            working_df,
            selected_return_address=selected_return_address,
            return_addresses_repo=self.mw.s.return_addresses_repo,
        )

        if use_max_service_dimensions:
            working_df = self.service_rules.apply_max_service_dimensions(
                working_df,
                ecom_services_repo=self.mw.s.ecom_services_repo,
                service_column="Service",
            )

        if paf_reject_df is not None and not paf_reject_df.empty:
            paf_reject_df = self._apply_all_info_fields(
                paf_reject_df,
                fields=fields,
                multiply_weight_by_quantity=multiply_weight_by_quantity,
                change_service_code=change_service_code,
                use_windsor_agreement_defaults=use_windsor_agreement_defaults,
            )

            paf_reject_df = self.transforms.apply_return_address(
                paf_reject_df,
                selected_return_address=selected_return_address,
                return_addresses_repo=self.mw.s.return_addresses_repo,
            )

            if use_max_service_dimensions:
                paf_reject_df = self.service_rules.apply_max_service_dimensions(
                    paf_reject_df,
                    ecom_services_repo=self.mw.s.ecom_services_repo,
                    service_column="Service",
                )

        return working_df, paf_reject_df

    def _run_service_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not resolution_state["rows"]:
            return {
                "rows": [],
                "original_rows": [],
                "mass_update": {},
            }

        dlg = ServiceResolutionDialog(
            resolution_state["rows"],
            valid_services=resolution_state["valid_services"],
            parent=self.mw,
        )
        if not dlg.exec():
            return None

        return {
            "rows": dlg.result_rows(),
            "original_rows": [dict(r or {}) for r in resolution_state["rows"]],
            "mass_update": dlg.mass_update_values(),
        }

    def _run_service_resolution_loop(
        self,
        df: pd.DataFrame,
        *,
        use_max_service_dimensions: bool = False,
    ) -> pd.DataFrame | None:
        rule_cache = self.service_rules.service_rule_cache(self.mw.s.ecom_services_repo)

        working_df = df.copy()

        while True:
            resolution_state = self.service_rules.collect_service_resolution_state(
                working_df,
                rule_cache=rule_cache,
            )

            if not resolution_state["rows"]:
                return working_df

            if not resolution_state["valid_services"]:
                self.warn(
                    "Resolve Services",
                    "No valid services are available for the current rejected rows.",
                )
                return None

            result = self._run_service_resolution_dialog_if_needed(
                resolution_state=resolution_state,
            )
            if result is None:
                return None

            working_df = self.service_rules.apply_service_resolution_result(
                working_df,
                resolution_indices=resolution_state["resolution_indices"],
                result=result,
                use_max_service_dimensions=use_max_service_dimensions,
                ecom_services_repo=self.mw.s.ecom_services_repo,
            )

    def _rename_reject_frame_to_paf(
        self,
        df: pd.DataFrame,
        *,
        preview_columns: list[str],
        town_col: str | None,
        county_col: str | None,
        postcode_col: str,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        return self.mapping.rename_to_paf_columns(
            df,
            preview_columns=preview_columns,
            town_col=town_col,
            county_col=county_col,
            postcode_col=postcode_col,
        )

    def _collect_recipient_name_resolution_state(
        self,
        df: pd.DataFrame,
        *,
        preview_specs: list[dict[str, str]],
    ) -> dict[str, Any]:
        if "Recipient Name" not in df.columns:
            return {
                "resolution_indices": [],
                "rows": [],
            }

        paf_address1_source = next(
            (
                str(spec.get("source"))
                for spec in preview_specs
                if str(spec.get("paf", "")).strip() == "PAF Address 1"
            ),
            None,
        )
        paf_town_source = next(
            (
                str(spec.get("source"))
                for spec in preview_specs
                if str(spec.get("paf", "")).strip() == "PAF Town"
            ),
            None,
        )

        def str_col(col):
            if col not in df.columns:
                return pd.Series([""] * len(df), index=df.index)
            return df[col].fillna("").astype(str).str.strip()

        missing_mask = str_col("Recipient Name").eq("") & str_col("Company").eq("")
        if not missing_mask.any():
            return {"resolution_indices": [], "rows": []}

        resolution_indices = [int(i) for i in df.index[missing_mask]]
        rows: list[dict[str, str]] = []
        for idx in df.index[missing_mask]:
            paf_address1 = ""
            if paf_address1_source and paf_address1_source in df.columns:
                v = df.at[idx, paf_address1_source]
                paf_address1 = "" if pd.isna(v) else str(v).strip()

            paf_town = ""
            if paf_town_source and paf_town_source in df.columns:
                v = df.at[idx, paf_town_source]
                paf_town = "" if pd.isna(v) else str(v).strip()

            rows.append({
                "Recipient Name": "",
                "Company": "",
                "PAF Address 1": paf_address1,
                "PAF Town": paf_town,
                "Reject Reason": "Recipient name missing",
            })

        return {"resolution_indices": resolution_indices, "rows": rows}
    
    def _run_recipient_name_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not resolution_state["rows"]:
            return {
                "rows": [],
                "original_rows": [],
                "removed": set(),
            }

        dlg = RecipientNameResolutionDialog(
            resolution_state["rows"],
            parent=self.mw,
        )
        if not dlg.exec():
            return None

        return {
            "rows": dlg.result_rows(),
            "original_rows": [dict(r or {}) for r in resolution_state["rows"]],
            "removed": dlg.removed_indices(),
        }

    def _apply_recipient_name_resolution_result(
        self,
        df: pd.DataFrame,
        *,
        resolution_indices: list[int],
        result: dict[str, Any],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        out = df.copy()
        reject_rows: list[pd.Series] = []

        edited_rows = list(result.get("rows", []) or [])
        original_rows = list(result.get("original_rows", []) or [])
        removed = set(result.get("removed") or set())

        kept_positions = [pos for pos in range(len(resolution_indices)) if pos not in removed]

        for pos in sorted(removed, reverse=True):
            if pos < 0 or pos >= len(resolution_indices):
                continue
            idx = resolution_indices[pos]
            if idx in out.index:
                reject_rows.append(out.loc[idx].copy())
                out.drop(index=idx, inplace=True)

        for new_pos, original_pos in enumerate(kept_positions):
            if new_pos >= len(edited_rows):
                continue

            idx = resolution_indices[original_pos]
            if idx not in out.index or "Recipient Name" not in out.columns:
                continue

            edited = edited_rows[new_pos]
            original = original_rows[original_pos] if original_pos < len(original_rows) else {}

            original_value = "" if pd.isna(original.get("Recipient Name")) else str(original.get("Recipient Name")).strip()
            edited_value = "" if pd.isna(edited.get("Recipient Name")) else str(edited.get("Recipient Name")).strip()

            if edited_value != original_value:
                out.loc[idx, "Recipient Name"] = edited_value

        out.reset_index(drop=True, inplace=True)

        reject_df = pd.DataFrame(reject_rows)
        if not reject_df.empty:
            reject_df.reset_index(drop=True, inplace=True)

        return out, reject_df

    def _run_recipient_name_resolution_loop(
        self,
        df: pd.DataFrame,
        *,
        preview_specs: list[dict[str, str]],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        working_df = df.copy()
        all_recipient_rejects: list[pd.DataFrame] = []

        while True:
            resolution_state = self._collect_recipient_name_resolution_state(
                working_df,
                preview_specs=preview_specs,
            )

            if not resolution_state["rows"]:
                reject_df = self.transforms.concat_frames(all_recipient_rejects)
                return working_df, reject_df

            result = self._run_recipient_name_resolution_dialog_if_needed(
                resolution_state=resolution_state,
            )
            if result is None:
                # Move remaining unresolved rows to rejects rather than letting
                # blank-name rows pass silently into the output file.
                unresolved_indices = resolution_state["resolution_indices"]
                if unresolved_indices:
                    unresolved_df = working_df.loc[unresolved_indices].copy()
                    unresolved_df.reset_index(drop=True, inplace=True)
                    all_recipient_rejects.append(unresolved_df)
                    working_df = working_df.drop(index=unresolved_indices).reset_index(drop=True)
                return working_df, self.transforms.concat_frames(all_recipient_rejects)

            working_df, reject_df = self._apply_recipient_name_resolution_result(
                working_df,
                resolution_indices=resolution_state["resolution_indices"],
                result=result,
            )

            if reject_df is not None and not reject_df.empty:
                all_recipient_rejects.append(reject_df)

    def _collect_field_length_resolution_state(
        self,
        df: pd.DataFrame,
    ) -> dict[str, Any]:
        available_columns = [col for col in FIELD_LENGTH_COLUMNS if col in df.columns]
        if not available_columns:
            return {"resolution_indices": [], "rows": []}

        # Build a clean string view of all field-length columns
        str_df = pd.DataFrame(index=df.index)
        for col in FIELD_LENGTH_COLUMNS:
            str_df[col] = df[col].fillna("").astype(str).str.strip() if col in df.columns else ""

        # Find rows where any non-blank value exceeds the limit
        too_long_df = str_df.apply(lambda s: s.str.len() > FIELD_LENGTH_LIMIT) & str_df.ne("")
        any_too_long = too_long_df.any(axis=1)

        if not any_too_long.any():
            return {"resolution_indices": [], "rows": []}

        resolution_indices = [int(i) for i in df.index[any_too_long]]
        rows: list[dict[str, str]] = []
        for idx in df.index[any_too_long]:
            row_data = {col: str_df.at[idx, col] for col in FIELD_LENGTH_COLUMNS}
            too_long = [
                f"{col} ({len(row_data[col])})"
                for col in FIELD_LENGTH_COLUMNS
                if row_data[col] and len(row_data[col]) > FIELD_LENGTH_LIMIT
            ]
            row_data["Reject Reason"] = (
                f"Will be truncated on label ({FIELD_LENGTH_LIMIT} max): " + ", ".join(too_long)
            )
            rows.append(row_data)

        return {"resolution_indices": resolution_indices, "rows": rows}

    def _run_field_length_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
    ) -> tuple[str, list[dict[str, str]]] | None:
        if not resolution_state["rows"]:
            return ("continue", [])

        dlg = FieldLengthResolutionDialog(
            resolution_state["rows"],
            parent=self.mw,
        )
        if not dlg.exec():
            return None

        return dlg.dialog_action(), dlg.result_rows()

    def _apply_field_length_resolution_result(
        self,
        df: pd.DataFrame,
        *,
        resolution_indices: list[int],
        original_rows: list[dict[str, str]],
        edited_rows: list[dict[str, str]],
    ) -> pd.DataFrame:
        out = df.copy()

        for row_pos, df_index in enumerate(resolution_indices):
            if row_pos >= len(edited_rows):
                continue

            if df_index not in out.index:
                continue

            edited = edited_rows[row_pos]
            original = original_rows[row_pos] if row_pos < len(original_rows) else {}

            for col in FIELD_LENGTH_COLUMNS:
                if col not in out.columns:
                    continue
                original_val = str(original.get(col, "")).strip()
                edited_val = "" if pd.isna(edited.get(col)) else str(edited.get(col)).strip()
                # Only write back values the user actually changed in the dialog.
                # Unchanged cells (including blank Recipient Name shown alongside a
                # long-address row) must not overwrite the live DataFrame value.
                if edited_val != original_val:
                    out.loc[df_index, col] = edited_val

        out.reset_index(drop=True, inplace=True)
        return out

    def _run_field_length_resolution_warning(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame | None:
        working_df = df.copy()

        while True:
            resolution_state = self._collect_field_length_resolution_state(working_df)
            if not resolution_state["rows"]:
                return working_df

            result = self._run_field_length_resolution_dialog_if_needed(
                resolution_state=resolution_state,
            )
            if result is None:
                return None

            action, edited_rows = result

            if action == "continue":
                return working_df

            if action == "update":
                working_df = self._apply_field_length_resolution_result(
                    working_df,
                    resolution_indices=resolution_state["resolution_indices"],
                    original_rows=resolution_state["rows"],
                    edited_rows=edited_rows,
                )
                # Loop back to re-check — edited values may still exceed the limit.

    def _build_batched_output_paths(
        self,
        outfile: str,
        *,
        total_rows: int,
        batch_size: int = 300,
    ) -> list[str]:
        base, ext = os.path.splitext(outfile)
        if not ext:
            ext = ".csv"

        if total_rows <= 0:
            return [outfile]

        num_batches = (total_rows + batch_size - 1) // batch_size
        return [f"{base} File {i}{ext}" for i in range(1, num_batches + 1)]

    def _save_output_in_batches(
        self,
        df: pd.DataFrame,
        *,
        outfile: str,
        title: str,
        delimiter: str,
        has_header: bool,
        batch_size: int = 300,
    ) -> None:
        if df is None or df.empty:
            self.save_csv_then(
                df,
                outfile,
                title=title,
                delimiter=delimiter,
                has_header=has_header,
                success_msg="E-Commerce file created successfully.",
                sanitize=True,
            )
            return

        paths = self._build_batched_output_paths(
            outfile,
            total_rows=len(df),
            batch_size=batch_size,
        )

        sanitized = self.sanitize_df_for_export(df)

        def job_save():
            saved = []
            start = 0
            for path in paths:
                chunk = sanitized.iloc[start:start + batch_size].copy()
                enc_label = self.mw._save_csv(chunk, path, has_header=has_header, delimiter=delimiter)
                saved.append((path, enc_label))
                start += batch_size
            return saved

        def on_done(saved):
            for i, (path, enc_label) in enumerate(saved, start=1):
                suffix = f" (Encoding: {enc_label})" if enc_label else ""
                self.info(f"Saved batch file {i}: {path}{suffix}", "green")

        self.busy(title, "Saving file…", job_save, on_done=on_done)