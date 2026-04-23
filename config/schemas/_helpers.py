from config.constants import SENTINEL_NONE, SENTINEL_SELECT


def _standard_default(standard_options):
    standard_options = standard_options or []
    return next(
        (o.get("value") for o in standard_options
            if str(o.get("label", "")).strip().lower() == "admail"),
        (standard_options[0].get("value") if standard_options else None))


def _seed_block(*, standard_options, bespoke_options, toggle_off_text, toggle_on_text):
    standard_options = standard_options or []
    bespoke_options = bespoke_options or []

    bespoke_opts_with_none = [{"label": "- None -", "value": SENTINEL_NONE}] + bespoke_options

    return {
        "type": "toggle_select",
        "key": "seeds",
        "label": "Seed Settings",
        "toggle": {"off": toggle_off_text, "on": toggle_on_text},
        "options": [],
        "default": "off",
        "extra": {
            "__enabled__": [
                {
                    "type": "select",
                    "label": "Standard",
                    "key": "standard_seed",
                    "options": standard_options,
                    "default": _standard_default(standard_options),
                },
                {
                    "type": "select",
                    "label": "Bespoke",
                    "key": "bespoke_seed",
                    "options": bespoke_opts_with_none,
                    "default": SENTINEL_NONE,
                },
            ]
        },
    }


def _info_switch(
    *,
    key_prefix,
    field_name,
    column_options,
    required=False,
    required_if=None,
    disabled_if=None,
):
    cfg = {
        "type": "switch_with_extras",
        "key": f"{key_prefix}_mode",
        "default": "a",
        "field_name": field_name,
        "always_required": bool(required),
        "state_name_a": f"Select {field_name}",
        "state_name_b": f"Enter {field_name}",
        "control_a": {
            "type": "compact_select",
            "key": f"{key_prefix}_column",
            "label": "",
            "options": column_options,
            "default": SENTINEL_SELECT,
            "mutex_group": "ecommerce_columns",
            "parent_mode_key": f"{key_prefix}_mode",
            "active_mode_value": "a",
        },
        "control_b": {
            "type": "text",
            "key": f"{key_prefix}_text",
            "label": "",
            "default": "",
        },
    }

    if required or required_if:
        cfg["required_mode_map"] = {
            "a": [f"{key_prefix}_column"],
            "b": [f"{key_prefix}_text"],
        }

    if required_if:
        cfg["required_if"] = required_if

    if disabled_if:
        cfg["disabled_if"] = disabled_if
        cfg["control_a"]["disabled_if"] = disabled_if
        cfg["control_b"]["disabled_if"] = disabled_if

    return cfg


def _poster_client_switch(*, key_prefix, field_name, options, full_width=False):
    return {
        "type": "switch_with_extras",
        "key": f"{key_prefix}_mode",
        "default": "a",
        "field_name": field_name,
        "full_width": full_width,
        "state_name_a": f"Select {field_name}",
        "state_name_b": f"Enter {field_name}",
        "control_a": {
            "type": "compact_select",
            "key": f"{key_prefix}_select",
            "label": "",
            "options": options,
            "default": SENTINEL_SELECT,
            "parent_mode_key": f"{key_prefix}_mode",
            "active_mode_value": "a",
        },
        "control_b": {
            "type": "text",
            "key": f"{key_prefix}_text",
            "label": "",
            "default": "",
        },
    }
