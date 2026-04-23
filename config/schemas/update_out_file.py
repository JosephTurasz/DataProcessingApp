from config.constants import SELECT_PLACEHOLDER
from config.schemas._helpers import _poster_client_switch


def build_update_out_file_schema(*, poster_options=None, client_options=None):
    poster_options = poster_options or [SELECT_PLACEHOLDER]
    client_options = client_options or [SELECT_PLACEHOLDER]

    _ucid_visible = {"key": "ucid_updates", "op": "!=", "value": "none"}

    return [
        {
            "type": "section",
            "label": "UCID Updates",
            "children": [
                {
                    "type": "radio_with_extras",
                    "key": "ucid_updates",
                    "label": "",
                    "orientation": "horizontal",
                    "default": "none",
                    "options": [
                        {
                            "label": "None",
                            "value": "none",
                            "extras": [],
                        },
                        {
                            "label": "1 UCID",
                            "value": "1",
                            "extras": [
                                {
                                    "type": "text",
                                    "label": "UCID",
                                    "key": "ucid1",
                                },
                            ],
                        },
                        {
                            "label": "2 UCIDs",
                            "value": "2",
                            "extras": [
                                {
                                    "type": "text",
                                    "label": "UCID 1",
                                    "key": "ucid1",
                                },
                                {
                                    "type": "text",
                                    "label": "UCID 2",
                                    "key": "ucid2",
                                },
                            ],
                        },
                    ],
                },
                {
                    **_poster_client_switch(
                        key_prefix="poster",
                        field_name="Poster",
                        options=poster_options,
                        full_width=True,
                    ),
                    "visible_if": _ucid_visible,
                },
                {
                    **_poster_client_switch(
                        key_prefix="client",
                        field_name="Client",
                        options=client_options,
                        full_width=True,
                    ),
                    "visible_if": _ucid_visible,
                },
            ],
        },
        {
            "type": "radio",
            "key": "barcode_padding",
            "label": "Barcode Padding",
            "options": [
                ("None", "none"),
                ("X", "X"),
                ("Z", "Z"),
            ],
            "default": "none",
        },
        {
            "type": "radio",
            "key": "barcode_type",
            "label": "Convert Barcode Type",
            "options": [
                ("None", "none"),
                ("Type 7 (51 Char)", "51"),
                ("Type 29 (70 Char)", "70"),
            ],
            "default": "none",
        },
    ]
