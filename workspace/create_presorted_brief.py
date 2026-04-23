from __future__ import annotations

import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

from processing.loading import load_bag, load_gemma
from workspace.base import BaseWorkflow

_COLUMNS = [
    "Poster",
    "Client",
    "Job Reference",
    "Job Description",
    "Sortation",
    "Machinability",
    "Format",
    "Mail Category",
    "Container Type",
    "Item Weight (g)",
    "Target Weight (g)",
    "No. Items",
    "No. Containers",
    "Collection Date",
]


class CreatePresortedBrief(BaseWorkflow):
    def run(self, checked: bool = False):
        paths = self.mw.ask_open_files(
            "Select .bag and .gemma files",
            "BAG/GEMMA Files (*.bag *.gemma);;All Files (*)",
        )
        if not paths:
            return

        bag_files = sorted(p for p in paths if p.lower().endswith(".bag"))
        gemma_files = sorted(p for p in paths if p.lower().endswith(".gemma"))

        if not bag_files:
            self.warn("No .bag file", "Please select exactly one .bag file.")
            return
        if len(bag_files) > 1:
            self.warn("Too many .bag files", "Maximum of 1 bag file allowed.")
            return
        if len(gemma_files) > 2:
            self.warn("Too many .gemma files", "Maximum of 2 gemma files allowed.")
            return

        # Validate and load gemma upfront so the result can be reused in the job
        gemma_data: dict = {}
        if gemma_files:
            try:
                gemma_data = load_gemma(gemma_files[0])
                if len(gemma_files) == 2:
                    g2 = load_gemma(gemma_files[1])
                    if gemma_data.get("producer-name", "") != g2.get("producer-name", ""):
                        self.warn("Gemma mismatch", "The two gemma files do not match.")
                        return
            except Exception as e:
                self.warn("Gemma parse error", f"Failed to parse gemma file: {e}")
                return

        bag_path = bag_files[0]

        outfile = self.mw.ask_save_csv(
            "Save Pre-sorted Brief as",
            "Excel Files (*.xlsx);;All Files (*)",
            defaultName="Presorted Brief.xlsx",
        )
        if not outfile:
            return

        def job():
            stem = os.path.splitext(os.path.basename(bag_path))[0]
            bag_opts, bag_df = load_bag(bag_path)

            poster = gemma_data.get("producer-name", "")
            client = bag_opts.get("Client", "")
            reference = bag_opts.get("JobRef", "").strip()
            description = bag_opts.get("JobDesc", "")
            container_type = bag_opts.get("ContainerType", "")
            item_weight = bag_opts.get("ItemWeight", "")
            collection_date = bag_opts.get("CollectionDate", "")

            items_numeric = pd.to_numeric(bag_df["Items"].astype(str).str.strip(), errors="coerce")

            try:
                num_items = int(items_numeric.sum())
            except Exception:
                num_items = ""

            try:
                max_items = items_numeric.max()
                weight_val = pd.to_numeric(str(item_weight).strip(), errors="coerce")
                target_weight = int(max_items * weight_val) if pd.notna(max_items) and pd.notna(weight_val) else ""
            except Exception:
                target_weight = ""

            try:
                # BagNo values are zero-padded strings (e.g. "001", "002"); the
                # highest number is the total container count.
                num_containers = int(
                    pd.to_numeric(bag_df["BagNo"].astype(str).str.strip(), errors="coerce").max()
                )
            except Exception:
                num_containers = ""

            warnings = []
            repo = self.mw.s.mailsort_services_repo
            service = repo.get_by_codes(
                format_code=bag_opts.get("Format", ""),
                sortation_code=bag_opts.get("Sortation", ""),
                machinability_code=bag_opts.get("Machinable", ""),
            )
            if service:
                fmt = service.get("format", "")
                sortation = service.get("sortation", "")
                machinability = service.get("machinability", "")
                mail_category = service.get("mail_category", "")
            else:
                fmt = sortation = machinability = mail_category = ""
                warnings.append(f"No service was found for {stem}")

            wb = Workbook()
            ws = wb.active
            ws.title = "Pre-sorted Brief"

            ws.append(_COLUMNS)
            for cell in ws[1]:
                cell.font = Font(bold=True)

            ws.append([
                poster, client, reference, description,
                sortation, machinability, fmt, mail_category,
                container_type, item_weight, target_weight, num_items, num_containers, collection_date,
            ])

            for col in ws.columns:
                max_len = max((len(str(cell.value or "")) for cell in col), default=0)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

            wb.save(outfile)
            return {"warnings": warnings}

        def on_done(result: dict):
            for w in result.get("warnings", []):
                self.info(f"Warning: {w}", "yellow")
            self.info("Pre-sorted Brief saved successfully.", "green")

        self.run_busy(
            "Create Pre-sorted Brief",
            "Processing…",
            job,
            on_done=on_done,
            on_err=lambda e: self.fail("Create Pre-sorted Brief failed", e),
        )
