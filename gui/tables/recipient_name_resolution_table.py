from __future__ import annotations

from gui.tables.resolution_table_base import ResolutionTableBase


class RecipientNameResolutionTable(ResolutionTableBase):
    HEADERS = ["Recipient Name", "Company", "PAF Address 1", "PAF Town", "Reject Reason"]
    EDITABLE_COLUMNS = {"Recipient Name"}
