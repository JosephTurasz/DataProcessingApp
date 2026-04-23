from config.constants import DELIMITER_OPTIONS, SELECT_PLACEHOLDER, SENTINEL_SELECT
from config.schemas._helpers import _seed_block


def build_create_file_schema(*, standard_options, bespoke_options, poster_options=None, client_options_provider=None):
    poster_options = poster_options or [SELECT_PLACEHOLDER]
    client_options_provider = client_options_provider or (lambda _poster: [SELECT_PLACEHOLDER])

    return [
        {
            "type": "section",
            "label": "Poster / Client",
            "children": [
                {
                    "type": "compact_select",
                    "key": "ucid_poster",
                    "label": "Poster",
                    "options": poster_options,
                    "default": SENTINEL_SELECT,
                    "required": False,
                    "full_width": True,
                },
                {
                    "type": "compact_select",
                    "key": "ucid_client",
                    "label": "Client",
                    "options": [SELECT_PLACEHOLDER],
                    "default": SENTINEL_SELECT,
                    "required": False,
                    "depends_on": "ucid_poster",
                    "options_provider": client_options_provider,
                    "full_width": True,
                },
            ],
        },
        _seed_block(
            standard_options=standard_options,
            bespoke_options=bespoke_options,
            toggle_off_text="None",
            toggle_on_text="Append Seeds",
        ),
        {
            "type": "toggle_select",
            "key": "mmi",
            "label": "MMI Settings",
            "toggle": {"off": "None", "on": "Append MMI"},
            "options": ["Coopers", "Scotts", "ProHub DMS"],
            "extra": {
                "Scotts": {
                    "type": "text",
                    "label": "Cell name",
                    "key": "cell_name",
                }
            },
            "default": "off",
        },
        {
            "key": "header_cleaning",
            "type": "radio",
            "label": "Header cleaning",
            "default": "none",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "Remove _", "value": "underscore"},
                {"label": "Remove .", "value": "dot"},
            ],
        },
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output Delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]
