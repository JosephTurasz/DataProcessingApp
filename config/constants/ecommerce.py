PAF_POSTCODE_COL = "PAF Postcode"
PAF_TOWN_COL     = "PAF Town"
PAF_COUNTY_COL   = "PAF County"

MAX_SERVICE_DIMENSIONS = {
    "Length": "400",
    "Width":  "300",
    "Height": "200",
}

DEFAULT_WINDSOR_DETAILS = {
    "Country Code":        "GB",
    "Retail Value":        1,
    "Product Description": "Printed Matter",
    "Quantity":            1,
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
    "postcode_column":            ["postcode", "post code", "postal code", "zip", "zip code", "mailing postcode", "mailing post code"],
    "town_column":                ["town", "city", "post town", "mailing town"],
    "county_column":              ["county", "mailing county", "province", "state", "region"],
    "name_column":                ["recipient name", "formatted name", "full name", "name", "first name", "forename", "recipient"],
    "surname_column":             ["surname", "last name", "family name", "second name"],
    "company_column":             ["company", "organisation", "organization", "business name", "company name"],
    "reference_column":           ["client item reference", "item reference", "order reference", "customer reference", "reference", "ref"],
    "service_column":             ["delivery service", "service code", "service", "shipping service"],
    "weight_column":              ["parcel weight", "item weight", "weight", "package weight"],
    "length_column":              ["length", "parcel length", "package length", "item length"],
    "width_column":               ["width", "parcel width", "package width", "item width"],
    "height_column":              ["height", "parcel height", "package height", "item height"],
    "country_code_column":        ["country code", "iso country code", "country iso", "iso code", "destination country code"],
    "quantity_column":            ["quantity", "qty", "item quantity", "number of items"],
    "product_description_column": ["product description", "item description", "description", "contents", "product"],
    "retail_value_column":        ["retail value", "declared value", "item value", "value"],
}
