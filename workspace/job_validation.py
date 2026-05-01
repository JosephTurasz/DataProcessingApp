from __future__ import annotations

import os
import re
from datetime import date, datetime

import openpyxl
from openpyxl.styles import Alignment, Font
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from processing.loading import load_bag, load_cpr, load_labels
from workspace.base import BaseWorkflow

_HEADER_SENTINELS = {"Client/Sub-Client Name", "Client to be Billed"}
_BRIEF_TYPES = {
    "client/sub-client name": "TDG Brief v2",
    "client to be billed":    "TDG Brief v1",
}

# Rename rules applied to header_values at the end of processing.
# Each entry is (substring_to_match, output_name); first match wins.
_HEADER_RENAME_RULES = [
    ("Client",           "Client"),
    ("Machineable",      "Machinability"),
    ("Container Fill",   "Container Fill"),
    ("Weight of Pack",   "Accurate Weight"),
    ("Number of Items",  "No. Items"),
    ("Date of Collection", "Collection Date"),
]
_JOB_HEADER_VARIANTS = {"Job Reference", "Job Name/Reference"}

# Maps output header display names → ImportOption keys in a .BAG.txt file
_BAG_FIELD_MAP = {
    "Client":          "Client",
    "Job Name":        "JobDesc",
    "Collection Date": "CollectionDate",
    "Accurate Weight": "ItemWeight",
    "Container":       "ContainerType",
}

# Runs of 5+ spaces are truncated from that point onward.
_SPACE_RUN_RE = re.compile(r" {5,}")
# Bracket content including the brackets themselves (round and square).
_BRACKET_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")


def _normalize_cell(val):
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y")
    if not isinstance(val, str):
        return val
    m = _SPACE_RUN_RE.search(val)
    return val[:m.start()] if m else val


def _clean_header(val):
    if not isinstance(val, str):
        return val
    return _BRACKET_RE.sub("", val).strip()


_NUMERIC_RE = re.compile(r"\d+(?:\.\d+)?")
_TRAY_FILL_RE = re.compile(r"\btray\s+fill\b", re.IGNORECASE)
_DIGITS_RE = re.compile(r"\d+")


def _to_numeric(val):
    """Extract the first number from val. Returns int if whole, float otherwise, or None."""
    if isinstance(val, (int, float)):
        return val
    m = _NUMERIC_RE.search(str(val or ""))
    if not m:
        return None
    n = float(m.group())
    return int(n) if n == int(n) else n


def _extract_container_fill(val):
    """Return the first integer from the 'Tray Fill ...' line, or val unchanged."""
    if not isinstance(val, str):
        return val
    for line in val.splitlines():
        if _TRAY_FILL_RE.search(line):
            m = _DIGITS_RE.search(line)
            if m:
                return int(m.group())
    return val


def _find_right_of(all_rows, label: str, *, partial: bool = False):
    """Return the first non-blank cell value to the right of the cell matching label."""
    label_lower = label.lower()
    for row in all_rows:
        for col_idx, cell_val in enumerate(row):
            s = str(cell_val or "").strip().lower()
            matched = (label_lower in s) if partial else (s == label_lower)
            if matched:
                for right_col in range(col_idx + 1, len(row)):
                    rv = row[right_col]
                    if rv is not None and str(rv).strip():
                        return _normalize_cell(rv)
                return None
    return None


def _has_line_break(val) -> bool:
    return isinstance(val, str) and ("\n" in val or "\r" in val)


def _col_idx(header_values: list, name: str) -> int | None:
    return next((i for i, hv in enumerate(header_values) if str(hv or "") == name), None)


class _JobSelectionDialog(QDialog):
    def __init__(self, job_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Job to Validate")
        self.selected_idx: int | None = None
        self.resize(340, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a job to validate:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        btn_layout = QVBoxLayout(container)
        btn_layout.setSpacing(6)

        for i, name in enumerate(job_names):
            btn = QPushButton(str(name))
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _select(self, idx: int):
        self.selected_idx = idx
        self.accept()


class JobValidation(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Select a brief",
            "Excel Files (*.xlsx)",
        )
        if not infile:
            return

        def job():
            wb = openpyxl.load_workbook(infile, read_only=True, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            wb.close()

            # Detect brief type and locate header row in one pass.
            # headers       — stripped logical names used for column matching
            # header_values — cleaned display values written to the output
            brief_type: str | None = None
            header_list_idx: int | None = None
            headers: list[str] = []
            header_values: list = []

            for i, row in enumerate(all_rows):
                col_a = str(row[0] or "").strip()
                bt = _BRIEF_TYPES.get(col_a.lower())
                if bt:
                    brief_type = bt
                    header_list_idx = i
                    headers = [col_a]
                    header_values = [_clean_header(_normalize_cell(row[0]))]
                    for val in row[1:]:
                        stripped = str(val or "").strip()
                        if not stripped:
                            break
                        headers.append(stripped)
                        header_values.append(_clean_header(_normalize_cell(val)))
                    break

            if brief_type is None:
                for row in all_rows:
                    for cell_val in row:
                        if str(cell_val or "").strip().lower() == "job name:":
                            brief_type = "Pureprint Brief"
                            break
                    if brief_type is not None:
                        break

            if brief_type is None:
                raise ValueError("Could not identify brief type. Is this a TDG or Pureprint brief?")

            if brief_type == "Pureprint Brief":
                def _r(label, *, partial=False):
                    return _find_right_of(all_rows, label, partial=partial)

                additional_parts = [
                    _r("Ad Mail/General Mail/Business Mail/Catalogue Mail:"),
                    _r("Partially Addressed:"),
                    _r("Magazine Subscription:"),
                ]
                additional_service = " / ".join(
                    str(p) for p in additional_parts if p is not None and str(p).strip()
                )

                container_fill = _to_numeric(_r("If Trays please specify tray fill", partial=True))
                item_weight = _to_numeric(_r("Item weight (g):"))
                target_weight = (
                    container_fill * item_weight
                    if container_fill is not None and item_weight is not None
                    else None
                )

                pp_headers = [
                    "Poster", "Client", "Job Name", "Service", "Format",
                    "Additional Service", "Machinability", "Container",
                    "Container Fill", "Accurate Weight", "Maximum Container Weight",
                    "Split Release", "No. Items", "Collection Date", "JIC Opt-In",
                ]
                pp_row = [
                    _r("Mailing House Name:"),
                    _r("Client Name:"),
                    _r("Job Name:"),
                    _r("Service:"),
                    _r("Item format:"),
                    additional_service or None,
                    None,
                    _r("Mail presentation:"),
                    container_fill,
                    item_weight,
                    target_weight,
                    None,
                    _to_numeric(_r("Number of items:")),
                    _r("Collection Date:"),
                    _r("JIC Opt in or Opt out:"),
                ]
                return pp_headers, [pp_row], pp_headers.index("Job Name"), brief_type

            # Find and rename the job column
            job_col_idx: int | None = None
            for i, h in enumerate(headers):
                if h in _JOB_HEADER_VARIANTS:
                    headers[i] = "Job Name"
                    header_values[i] = "Job Name"
                    job_col_idx = i
                    break

            if job_col_idx is None:
                variants = " or ".join(f'"{v}"' for v in sorted(_JOB_HEADER_VARIANTS))
                raise ValueError(f"Could not find {variants} in the header row.")

            # Collect data rows — stop at first blank in the job column
            rows_data: list[list] = []
            for row in all_rows[header_list_idx + 1:]:
                job_val = str(row[job_col_idx] or "").strip() if len(row) > job_col_idx else ""
                if not job_val:
                    break
                row_data = [
                    _normalize_cell(row[col_idx]) if len(row) > col_idx else None
                    for col_idx in range(len(headers))
                ]
                rows_data.append(row_data)

            # TDG Brief v1: Container Fill is absent — insert it and populate from
            # the cell below "Additional Information" elsewhere in the sheet.
            if brief_type == "TDG Brief v1":
                container_idx = next(
                    (i for i, hv in enumerate(header_values) if str(hv or "").strip() == "Container"), None
                )
                if container_idx is not None:
                    insert_at = container_idx + 1
                    headers.insert(insert_at, "Max Container Fill")
                    header_values.insert(insert_at, "Max Container Fill")
                    for row_data in rows_data:
                        row_data.insert(insert_at, None)
                    if job_col_idx >= insert_at:
                        job_col_idx += 1

                    max_fill_value = None
                    found = False
                    for row_idx, row in enumerate(all_rows):
                        for col_idx, cell_val in enumerate(row):
                            if str(cell_val or "").strip().lower() == "additional information":
                                next_row = all_rows[row_idx + 1] if row_idx + 1 < len(all_rows) else []
                                raw = next_row[col_idx] if col_idx < len(next_row) else None
                                max_fill_value = _extract_container_fill(_normalize_cell(raw))
                                found = True
                                break
                        if found:
                            break
                    if max_fill_value is not None:
                        for row_data in rows_data:
                            row_data[insert_at] = max_fill_value

            # TDG Brief v2: Container Fill column is already present in the brief.

            # Insert "Maximum Container Weight" (Max Container Fill × Pack Weight) after pack weight
            pack_w_idx = next(
                (i for i, hv in enumerate(header_values) if "Weight of Pack" in str(hv or "")), None
            )
            fill_idx = next(
                (i for i, hv in enumerate(header_values) if "Container Fill" in str(hv or "")), None
            )
            if pack_w_idx is not None and fill_idx is not None:
                twc_at = pack_w_idx + 1
                headers.insert(twc_at, "Maximum Container Weight")
                header_values.insert(twc_at, "Maximum Container Weight")
                if job_col_idx >= twc_at:
                    job_col_idx += 1
                if fill_idx >= twc_at:
                    fill_idx += 1
                for row_data in rows_data:
                    row_data.insert(twc_at, None)
                    pack_w = _to_numeric(row_data[pack_w_idx])
                    fill = _to_numeric(row_data[fill_idx])
                    if pack_w is not None and fill is not None:
                        row_data[twc_at] = pack_w * fill

            # Insert "Poster" as the first column — value is the first non-blank cell
            # to the right of any cell containing "Delivery Address"
            poster_value = None
            found = False
            for row_idx, row in enumerate(all_rows):
                for col_idx, cell_val in enumerate(row):
                    if "company name" in str(cell_val or "").strip().lower():
                        for right_col in range(col_idx + 1, len(row)):
                            right_val = row[right_col]
                            if right_val is not None and str(right_val).strip():
                                poster_value = _normalize_cell(right_val)
                                break
                        found = True
                        break
                if found:
                    break

            headers.insert(0, "Poster")
            header_values.insert(0, "Poster")
            job_col_idx += 1
            for row_data in rows_data:
                row_data.insert(0, poster_value)

            # Apply final display renames to header_values
            for i, hv in enumerate(header_values):
                s = str(hv or "")
                for substr, new_name in _HEADER_RENAME_RULES:
                    if substr in s:
                        header_values[i] = new_name
                        break

            return header_values, rows_data, job_col_idx, brief_type

        def on_done(result: tuple):
            header_values, rows_data, job_col_idx, brief_type = result

            self.info(f"[BRIEF] {brief_type} detected.", "green")

            if not rows_data:
                self.warn("Job Validation", "No job rows found in the brief.")
                return

            if len(rows_data) == 1:
                selected_row = rows_data[0]
            else:
                job_names = [str(row[job_col_idx] or "") for row in rows_data]
                dlg = _JobSelectionDialog(job_names, parent=self.mw)
                if dlg.exec() != QDialog.Accepted or dlg.selected_idx is None:
                    return
                selected_row = rows_data[dlg.selected_idx]

            validation_files = self.mw.ask_open_files(
                "Select files to validate",
                "Validation Files (*.BAG.txt *.CPR.txt *.LABELS.txt);;All Files (*)",
            )
            if not validation_files:
                return

            job_name = str(selected_row[job_col_idx] or "")
            out_path = os.path.join(os.path.dirname(infile), f"{job_name} Validation File.xlsx")

            def write_output():
                out_wb = openpyxl.Workbook()
                out_ws = out_wb.active

                out_ws.append(["Source"] + header_values)
                for cell in out_ws[1]:
                    cell.font = Font(bold=True)
                    if _has_line_break(cell.value):
                        cell.alignment = Alignment(wrap_text=True)

                out_ws.append(["Brief"] + selected_row)
                row_num = out_ws.max_row
                out_ws.cell(row=row_num, column=1).font = Font(bold=True)
                for col_idx, val in enumerate(selected_row, start=2):
                    if _has_line_break(val):
                        out_ws.cell(row=row_num, column=col_idx).alignment = Alignment(wrap_text=True)

                bag_files    = [f for f in validation_files if f.upper().endswith(".BAG.TXT")]
                cpr_files    = [f for f in validation_files if f.upper().endswith(".CPR.TXT")]
                labels_files = [f for f in validation_files if f.upper().endswith(".LABELS.TXT")]
                val_row = [None] * len(header_values)

                if bag_files:
                    try:
                        bag_opts, _ = load_bag(bag_files[0])
                        for i, hv in enumerate(header_values):
                            opt_key = _BAG_FIELD_MAP.get(str(hv or ""))
                            if opt_key:
                                val_row[i] = bag_opts.get(opt_key)
                    except Exception as e:
                        self.info(f"[BAG] Could not read BAG file: {e}", "yellow")

                if cpr_files:
                    try:
                        cpr_data = load_cpr(cpr_files[0])

                        total_items = cpr_data.get("Total Items Processed", "")
                        if total_items:
                            idx = _col_idx(header_values, "No. Items")
                            if idx is not None:
                                val_row[idx] = _to_numeric(total_items.replace(",", ""))

                        max_bag_weight = cpr_data.get("Maximum Bag Weight", "")
                        if max_bag_weight:
                            idx = _col_idx(header_values, "Maximum Container Weight")
                            if idx is not None:
                                val_row[idx] = _to_numeric(max_bag_weight.replace(",", ""))

                        service_name = cpr_data.get("Service Selected", "")
                        if service_name:
                            svc = self.mw.s.mailsort_services_repo.get_by_service_name(service_name)
                            if svc:
                                sortation = str(svc.get("sortation", "") or "").strip()
                                machinability = str(svc.get("machinability", "") or "").strip()
                                service_str = " / ".join(filter(None, [sortation, machinability]))
                                _set = {
                                    "Service":            service_str,
                                    "Format":             str(svc.get("format", "") or "").strip(),
                                    "Additional Service": str(svc.get("mail_category", "") or "").strip(),
                                }
                                for i, hv in enumerate(header_values):
                                    v = _set.get(str(hv or ""))
                                    if v is not None:
                                        val_row[i] = v
                    except Exception as e:
                        self.info(f"[CPR] Could not read CPR file: {e}", "yellow")

                if labels_files:
                    try:
                        labels_data = load_labels(labels_files[0])
                        poster = labels_data.get("Poster", "")
                        if poster:
                            idx = _col_idx(header_values, "Poster")
                            if idx is not None:
                                val_row[idx] = poster
                    except Exception as e:
                        self.info(f"[LABELS] Could not read LABELS file: {e}", "yellow")

                if any(v is not None for v in val_row):
                    out_ws.append(["Data files"] + val_row)
                    row_num = out_ws.max_row
                    out_ws.cell(row=row_num, column=1).font = Font(bold=True)

                try:
                    out_wb.save(out_path)
                except PermissionError:
                    raise PermissionError(
                        f"Could not save '{os.path.basename(out_path)}'.\n\nPlease close the file in Excel and try again."
                    )

            def on_written(_):
                self.info(f"Job Validation file created for: {job_name}", "green")
                os.startfile(out_path)

            self.busy("Job Validation", "Writing validation file…", write_output, on_done=on_written)

        self.busy("Job Validation", "Reading brief…", job, on_done=on_done)
