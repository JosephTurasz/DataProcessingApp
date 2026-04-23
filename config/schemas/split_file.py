from config.constants import DELIMITER_OPTIONS, SELECT_PLACEHOLDER, SENTINEL_NONE, SENTINEL_SELECT


def build_split_file_schema(*, standard_options, bespoke_options, poster_options=None, client_options_provider=None):
    standard_options = standard_options or []
    bespoke_options = bespoke_options or []
    poster_options = poster_options or [SELECT_PLACEHOLDER]
    client_options_provider = client_options_provider or (lambda _poster: [SELECT_PLACEHOLDER])

    bespoke_opts_with_none = [{"label": "- None -", "value": SENTINEL_NONE}] + bespoke_options

    return [
        {
            "type": "radio",
            "key": "split_mode",
            "label": "Split mode",
            "options": [
                ("Split by column", "column"),
                ("Split by number of items", "items"),
            ],
            "default": "column",
        },
        {
            "type": "number",
            "key": "items_file1",
            "label": "File 1 items",
            "default": 0,
            "min": 0,
            "visible_if": {"key": "split_mode", "op": "==", "value": "items"},
        },
        {
            "type": "number",
            "key": "items_file2",
            "label": "File 2 items",
            "default": 0,
            "min": 0,
            "visible_if": {"key": "split_mode", "op": "==", "value": "items"},
        },
        {
            "type": "select",
            "key": "split_column",
            "label": "Column to split by",
            "options": [],
            "default": SENTINEL_SELECT,
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "radio",
            "key": "split_count",
            "label": "Number of files",
            "options": [("2", 2), ("3", 3), ("4", 4), ("5", 5)],
            "default": 2,
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "multi_select",
            "key": "file1_values",
            "label": "File 1",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "multi_select",
            "key": "file2_values",
            "label": "File 2",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "multi_select",
            "key": "file3_values",
            "label": "File 3",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 3},
        },
        {
            "type": "multi_select",
            "key": "file4_values",
            "label": "File 4",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 4},
        },
        {
            "type": "multi_select",
            "key": "file5_values",
            "label": "File 5",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 5},
        },
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
        {
            "type": "radio_with_shared_extras",
            "key": "seeds_mode",
            "label": "Seed Settings",
            "orientation": "horizontal",
            "disable_value": "none",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "First File", "value": "file1"},
                {"label": "All Files", "value": "all"},
            ],
            "default": "none",
            "shared_extras": [
                {
                    "type": "labeled_select_row",
                    "label": "Standard",
                    "key": "standard_seed",
                    "options": standard_options,
                    "default": None,
                    "label_width": 80,
                },
                {
                    "type": "labeled_select_row",
                    "label": "Bespoke",
                    "key": "bespoke_seed",
                    "options": bespoke_opts_with_none,
                    "default": SENTINEL_NONE,
                    "label_width": 80,
                },
            ],
        },
        {
            "type": "toggle_select",
            "key": "mmi",
            "label": "MMI",
            "toggle": {"off": "None", "on": "Append"},
            "options": [
                ("Coopers", "Coopers"),
                ("Scotts", "Scotts"),
                ("ProHub DMS", "ProHub DMS"),
            ],
            "extra": {
                "Scotts": [
                    {
                        "type": "text",
                        "key": "cell_name",
                        "label": "Cell name",
                    }
                ]
            },
        },
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output Delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]
