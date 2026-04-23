from config.constants import DELIMITER_OPTIONS, SELECT_PLACEHOLDER, SENTINEL_SELECT
from config.schemas._helpers import _info_switch


def build_create_ecommerce_file_schema(*, column_options, preview_rows=None, return_address_options=None):
    return_address_options = return_address_options or [SELECT_PLACEHOLDER]

    return [
        {
            "type": "table_preview",
            "key": "file_preview",
            "label": "Preview (first 10 rows)",
            "rows": preview_rows or [],
        },
        {
            "type": "section",
            "label": "Address Fields (Fields marked with * are mandatory)",
            "children": [
                {
                    "type": "compact_select_row",
                    "children": [
                        {
                            "type": "range_select",
                            "key": "address_fields",
                            "start_key": "address_start",
                            "end_key": "address_end",
                            "start_label": "Address Start*",
                            "end_label": "Address End*",
                            "options": column_options,
                            "default_start": SENTINEL_SELECT,
                            "default_end": SENTINEL_SELECT,
                            "required_keys": ["address_start", "address_end"],
                        },
                        {
                            "type": "compact_select",
                            "key": "town_column",
                            "label": "Town*",
                            "options": column_options,
                            "default": SENTINEL_SELECT,
                            "required": True,
                            "mutex_group": "ecommerce_columns",
                        },
                        {
                            "type": "compact_select",
                            "key": "county_column",
                            "label": "County",
                            "options": column_options,
                            "default": SENTINEL_SELECT,
                            "required": False,
                            "mutex_group": "ecommerce_columns",
                        },
                        {
                            "type": "compact_select",
                            "key": "postcode_column",
                            "label": "Postcode*",
                            "options": column_options,
                            "default": SENTINEL_SELECT,
                            "required": True,
                            "mutex_group": "ecommerce_columns",
                        },
                        {
                            "type": "compact_select",
                            "key": "return_address",
                            "label": "Return Address",
                            "options": return_address_options,
                            "default": SENTINEL_SELECT,
                            "required": False,
                        },
                    ],
                },
            ],
        },
        {
            "type": "section",
            "label": "Recipient Details",
            "children": [
                {
                    "type": "compact_select_row",
                    "children": [
                        _info_switch(
                            key_prefix="name",
                            field_name="Name",
                            column_options=column_options,
                            required=True,
                        ),
                        _info_switch(
                            key_prefix="surname",
                            field_name="Surname",
                            column_options=column_options,
                            required=False,
                        ),
                        _info_switch(
                            key_prefix="company",
                            field_name="Company",
                            column_options=column_options,
                            required=False,
                        ),
                    ],
                },
            ],
        },
        {
            "type": "section",
            "label": "Options",
            "children": [
                {
                    "type": "compact_select_row",
                    "children": [
                        {
                            "type": "checkbox",
                            "key": "change_service_code",
                            "label": "Use Old Service Code",
                            "default": True,
                        },
                        {
                            "type": "checkbox",
                            "key": "use_max_service_dimensions",
                            "label": "Use Max Service Dimensions",
                            "default": False,
                        },
                        {
                            "type": "checkbox",
                            "key": "use_windsor_agreement_defaults",
                            "label": "Use Windsor Agreement Defaults",
                            "default": False,
                        },
                        {
                            "type": "checkbox",
                            "key": "multiply_weight_by_quantity",
                            "label": "Multiply Weight x Quantity",
                            "default": False,
                        },
                        {
                            "type": "checkbox",
                            "key": "export_in_batches_of_300",
                            "label": "Export in batches of 300",
                            "default": False,
                        }
                    ],
                },
            ],
        },
        {
            "type": "section",
            "label": "Service Details",
            "children": [
                {
                    "type": "compact_select_row",
                    "children": [
                        _info_switch(
                            key_prefix="reference",
                            field_name="Reference",
                            column_options=column_options,
                            required=True,
                        ),
                        _info_switch(
                            key_prefix="service",
                            field_name="Service",
                            column_options=column_options,
                            required=True,
                        ),
                        _info_switch(
                            key_prefix="weight",
                            field_name="Weight",
                            column_options=column_options,
                            required=True,
                        ),
                    ],
                },
                {
                    "type": "compact_select_row",
                    "children": [
                        _info_switch(
                            key_prefix="length",
                            field_name="Length",
                            column_options=column_options,
                            required=True,
                        ),
                        _info_switch(
                            key_prefix="width",
                            field_name="Width",
                            column_options=column_options,
                            required=True,
                        ),
                        _info_switch(
                            key_prefix="height",
                            field_name="Height",
                            column_options=column_options,
                            required=True,
                        ),
                    ],
                },
                {
                    "type": "compact_select_row",
                    "children": [
                        _info_switch(
                            key_prefix="country_code",
                            field_name="Country Code",
                            column_options=column_options,
                            required=False,
                            disabled_if={
                                "key": "use_windsor_agreement_defaults",
                                "op": "==",
                                "value": True,},
                        ),
                        _info_switch(
                            key_prefix="quantity",
                            field_name="Quantity",
                            column_options=column_options,
                            required=False,
                            required_if={
                                "key": "multiply_weight_by_quantity",
                                "op": "==",
                                "value": True,
                            },
                            disabled_if={
                                "key": "use_windsor_agreement_defaults",
                                "op": "==",
                                "value": True,
                            },
                        ),
                        _info_switch(
                            key_prefix="product_description",
                            field_name="Product Description",
                            column_options=column_options,
                            required=False,
                            disabled_if={
                                "key": "use_windsor_agreement_defaults",
                                "op": "==",
                                "value": True},
                        ),
                    ],
                },
                {
                    "type": "compact_select_row",
                    "children": [
                        _info_switch(
                            key_prefix="retail_value",
                            field_name="Retail Value",
                            column_options=column_options,
                            required=False,
                            disabled_if={
                                "key": "use_windsor_agreement_defaults",
                                "op": "==",
                                "value": True},
                        ),
                    ],
                },
            ],
        },
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]
