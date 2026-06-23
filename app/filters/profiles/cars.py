"""Filter profile for SS.lv transport/cars category.

Defines the canonical field mapping, value normalisation and display order
for car searches on SS.lv.

SS.lv transport/cars filter keys observed in the wild:

  opt[14]            – make (Марка / Marka / Make)
  opt[17]            – price from
  opt[32]            – price to
  topt[17][min/max]  – price range form
  topt[8][min/max]   – year (Год / Gads / Year)
  topt[10][min/max]  – mileage km (Пробег / Nobraukums / Mileage)
  topt[11][min/max]  – engine volume cm³ (Объём / Tilpums / Engine vol)
  opt[4]             – fuel type (Топливо / Degviela / Fuel)
  opt[5]             – gearbox (КПП / Ātrumkārba / Gearbox)
  opt[3]             – body type (Кузов / Virsbūve / Body)
  opt[6]             – color (Цвет / Krāsa / Color)
  pr_min / pr_max    – price range alternative
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Raw SS.lv key → canonical field name
# ---------------------------------------------------------------------------

RAW_TO_CANONICAL: dict[str, str] = {
    # make / model
    "opt[14]": "make",
    # price
    "opt[17]":      "price_min",
    "opt[32]":      "price_max",
    "topt[17][min]": "price_min",
    "topt[17][max]": "price_max",
    "pr_min":        "price_min",
    "pr_max":        "price_max",
    "price_min":     "price_min",
    "price_max":     "price_max",
    # year
    "topt[8][min]": "year_min",
    "topt[8][max]": "year_max",
    # mileage
    "topt[10][min]": "mileage_min",
    "topt[10][max]": "mileage_max",
    # engine volume
    "topt[11][min]": "engine_min",
    "topt[11][max]": "engine_max",
    # fuel
    "opt[4]": "fuel",
    # gearbox
    "opt[5]": "gearbox",
    # body type
    "opt[3]": "body_type",
    # color
    "opt[6]": "color",
}

# ---------------------------------------------------------------------------
# Human-readable labels per canonical field
# ---------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    "make":         {"lv": "Marka", "ru": "Марка", "en": "Make"},
    "year_min":     {"lv": "Gads (no)", "ru": "Год (от)", "en": "Year (from)"},
    "year_max":     {"lv": "Gads (līdz)", "ru": "Год (до)", "en": "Year (to)"},
    "mileage_min":  {"lv": "Nobraukums, km (no)", "ru": "Пробег, км (от)", "en": "Mileage, km (from)"},
    "mileage_max":  {"lv": "Nobraukums, km (līdz)", "ru": "Пробег, км (до)", "en": "Mileage, km (to)"},
    "engine_min":   {"lv": "Tilpums, cm³ (no)", "ru": "Объём, см³ (от)", "en": "Engine, cm³ (from)"},
    "engine_max":   {"lv": "Tilpums, cm³ (līdz)", "ru": "Объём, см³ (до)", "en": "Engine, cm³ (to)"},
    "fuel":         {"lv": "Degviela", "ru": "Топливо", "en": "Fuel"},
    "gearbox":      {"lv": "Ātrumkārba", "ru": "КПП", "en": "Gearbox"},
    "body_type":    {"lv": "Virsbūves tips", "ru": "Тип кузова", "en": "Body type"},
    "color":        {"lv": "Krāsa", "ru": "Цвет", "en": "Color"},
    "price_min":    {"lv": "Cena no, €", "ru": "Цена от, €", "en": "Price from, €"},
    "price_max":    {"lv": "Cena līdz, €", "ru": "Цена до, €", "en": "Price to, €"},
}

# ---------------------------------------------------------------------------
# Option value maps: raw value → human-readable label
# ---------------------------------------------------------------------------

OPTION_VALUES: dict[str, dict[str, dict[str, str]]] = {
    "fuel": {
        "1": {"lv": "Benzīns", "ru": "Бензин", "en": "Petrol"},
        "2": {"lv": "Dīzelis", "ru": "Дизель", "en": "Diesel"},
        "3": {"lv": "Gāze", "ru": "Газ", "en": "Gas"},
        "4": {"lv": "Hibrīds", "ru": "Гибрид", "en": "Hybrid"},
        "6": {"lv": "Elektriskais", "ru": "Электро", "en": "Electric"},
    },
    "gearbox": {
        "1": {"lv": "Manuāla", "ru": "Механика", "en": "Manual"},
        "2": {"lv": "Automāts", "ru": "Автомат", "en": "Automatic"},
        "3": {"lv": "Robota", "ru": "Робот", "en": "Robot"},
        "4": {"lv": "Variators", "ru": "Вариатор", "en": "CVT"},
    },
    "body_type": {
        "1":  {"lv": "Sedans", "ru": "Седан", "en": "Sedan"},
        "2":  {"lv": "Universāls", "ru": "Универсал", "en": "Estate"},
        "3":  {"lv": "Hečbeks", "ru": "Хэтчбек", "en": "Hatchback"},
        "4":  {"lv": "Kupe", "ru": "Купе", "en": "Coupe"},
        "5":  {"lv": "Kabriolets", "ru": "Кабриолет", "en": "Convertible"},
        "6":  {"lv": "Minivens", "ru": "Минивэн", "en": "Minivan"},
        "7":  {"lv": "SUV/Džips", "ru": "Внедорожник", "en": "SUV"},
        "8":  {"lv": "Pikaps", "ru": "Пикап", "en": "Pickup"},
        "9":  {"lv": "Mikroautobuss", "ru": "Микроавтобус", "en": "Microbus"},
    },
}

# ---------------------------------------------------------------------------
# Display order (canonical field names; unlisted fields go last)
# ---------------------------------------------------------------------------

DISPLAY_ORDER: list[str] = [
    "make",
    "year_min",
    "year_max",
    "mileage_min",
    "mileage_max",
    "engine_min",
    "engine_max",
    "fuel",
    "gearbox",
    "body_type",
    "color",
    "price_min",
    "price_max",
]

# ---------------------------------------------------------------------------
# Units / suffixes
# ---------------------------------------------------------------------------

UNITS: dict[str, str] = {
    "mileage_min": "км",
    "mileage_max": "км",
    "engine_min":  "см³",
    "engine_max":  "см³",
}
