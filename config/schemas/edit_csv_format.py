from config.constants import DELIMITER_OPTIONS


EDIT_CSV_FORMAT_SCHEMA = [
    {
        "type": "radio",
        "key": "header_cleaning",
        "label": "Header cleaning",
        "options": [
            ("None", "none"),
            ("Remove _", "underscore"),
            ("Remove .", "dot"),
        ],
        "default": "none",
    },
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output delimiter",
        "options": DELIMITER_OPTIONS,
        "default": ",",
    },
]
