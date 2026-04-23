from __future__ import annotations

from gui.tables.resolution_table_base import ResolutionTableBase


class FieldLengthResolutionTable(ResolutionTableBase):
    HEADERS = [
        "Recipient Name",
        "Company",
        "PAF Address 1",
        "PAF Address 2",
        "PAF Address 3",
        "PAF Town",
        "PAF County",
        "Reject Reason",
    ]
    EDITABLE_COLUMNS = {
        "Recipient Name",
        "Company",
        "PAF Address 1",
        "PAF Address 2",
        "PAF Address 3",
        "PAF Town",
        "PAF County",
    }
    WORD_WRAP = True
