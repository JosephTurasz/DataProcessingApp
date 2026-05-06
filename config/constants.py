APP_TITLE = "Data processing application."

# Sentinel values used in dropdowns/options schemas
SENTINEL_SELECT = "__select__"
SENTINEL_NONE = "__none__"
SELECT_PLACEHOLDER = ("— Select —", SENTINEL_SELECT)

DELIMITER_OPTIONS = [("Comma (,)", ","),
                     ("Semicolon (;)", ";"),
                     ("Tab", "\t"),
                     ("Pipe (|)", "|")]
# =========================
# ECOMMERCE CONSTANTS
# =========================
PAF_POSTCODE_COL = "PAF Postcode"
PAF_TOWN_COL = "PAF Town"
PAF_COUNTY_COL = "PAF County"

MAX_SERVICE_DIMENSIONS = {
    "Length": "400",
    "Width": "300",
    "Height": "200",
}

DEFAULT_WINDSOR_DETAILS = {
    "Country Code": "GB",
    "Retail Value": 1,
    "Product Description": "Printed Matter",
    "Quantity": 1
}

FIELD_LENGTH_LIMIT = 35
FIELD_LENGTH_COLUMNS = [
    "Recipient Name",
    "Company",
    "PAF Address 1",
    "PAF Address 2",
    "PAF Address 3",
    "PAF Town",
    "PAF County",
]

CHANNEL_ISLANDS_NAMES: frozenset[str] = frozenset({
    "jersey", "guernsey", "alderney", "sark", "herm",
    "jethou", "brecqhou", "brechou", "lihou",
})

ECOMMERCE_HEADER_SYNONYMS: dict[str, list[str]] = {
    "postcode_column": ["postcode", "post code", "postal code", "zip", "zip code","mailing postcode", "mailing post code"],
    "town_column": ["town", "city", "post town", "mailing town"],
    "county_column": ["county", "mailing county", "province", "state", "region"],
    "name_column": ["recipient name", "formatted name", "full name", "name","first name", "forename", "recipient"],
    "surname_column": ["surname", "last name", "family name", "second name"],
    "company_column": ["company", "organisation", "organization", "business name", "company name"],
    "reference_column": ["client item reference", "item reference", "order reference","customer reference", "reference", "ref"],
    "service_column": ["delivery service", "service code", "service", "shipping service"],
    "weight_column": ["parcel weight", "item weight", "weight", "package weight"],
    "length_column": ["length", "parcel length", "package length", "item length"],
    "width_column": ["width", "parcel width", "package width", "item width"],
    "height_column": ["height", "parcel height", "package height", "item height"],
    "country_code_column": ["country code", "iso country code", "country iso", "iso code", "destination country code"],
    "quantity_column": ["quantity", "qty", "item quantity", "number of items"],
    "product_description_column": ["product description", "item description", "description", "contents", "product"],
    "retail_value_column": ["retail value", "declared value", "item value", "value"]}
# =========================
# PRINTING CONSTANTS
# =========================
PDF_LABEL_WIDTH_PT = 288
PDF_LABEL_HEIGHT_PT = 432
PDF_LABEL_FONT = "helv"
PDF_LABEL_FONT_SIZE = 24
PDF_LABEL_ROTATE = 90

SYSTEM_PRINTERS = [
    r"\\TDG-FP01\DPWarLabel01",
    r"\\TDG-FP01\DPWarLabel02",
    r"\\TDG-FP01\DPWarLabel03",
    r"\\TDG-FP01\DPWarLabel04",
    r"\\TDG-FP01\DPWarLabel05",
    r"\\TDG-FP01\DPWarLabel06",
]
# =========================
# GUI / TABLE CONSTANTS
# =========================
# Drag/drop table ergonomics
TABLE_EDGE_GRAB_PX = 4
TABLE_SCROLL_MARGIN_PX = 24
TABLE_SCROLL_INTERVAL_MS = 120
# Preview dialog default size
PREVIEW_WIDTH = 1500
PREVIEW_HEIGHT = 750
# Undo history cap (preview-table edits keep full DataFrame snapshots)
PREVIEW_UNDO_LIMIT = 50
# Main window sizing
MAIN_WINDOW_MIN_WIDTH = 760
MAIN_WINDOW_MIN_HEIGHT = 580
# =========================
# WORKFLOW GUARDRAILS
# =========================
# Split-file heuristics
SPLIT_MAX_UNIQUE = 20
# CSV sniffing
CSV_SNIFF_BYTES = 8192
# Busy job defaults
BUSY_THREAD_SHUTDOWN_MS = 2000
# Sentinel raised by cancelable jobs to indicate user cancellation
CANCELLED_MSG = "__CANCELLED__"