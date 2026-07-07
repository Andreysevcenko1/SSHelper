"""Filter profile for SS.lv transport/cars category.

Defines the canonical field mapping, value normalisation and display order
for car searches on SS.lv.

SS.lv transport/cars filter keys observed in the wild:

  opt[14]            – make/brand (Марка / Marka / Brand)
  opt[15]            – model (Модель / Modelis / Model)
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

from app.i18n import get_text
from app.services.filter_registry import CARS_DM_FILTER_REGISTRY

# ---------------------------------------------------------------------------
# Raw SS.lv key → canonical field name
# ---------------------------------------------------------------------------

RAW_TO_CANONICAL: dict[str, str] = {
    raw_key: spec.canonical_key
    for spec in CARS_DM_FILTER_REGISTRY
    for raw_key in spec.raw_keys
}

# ---------------------------------------------------------------------------
# Human-readable labels per canonical field
# ---------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    spec.canonical_key: {
        "lv": get_text(spec.label_i18n_key, "lv"),
        "ru": get_text(spec.label_i18n_key, "ru"),
        "en": get_text(spec.label_i18n_key, "en"),
    }
    for spec in CARS_DM_FILTER_REGISTRY
}

# ---------------------------------------------------------------------------
# Option value maps: raw value → human-readable label
# ---------------------------------------------------------------------------

OPTION_VALUES: dict[str, dict[str, dict[str, str]]] = {
    "engine_type": {
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
    # Popular brands used in DM UX (fallback to raw value if unknown).
    "brand": {
        "BMW": {"lv": "BMW", "ru": "BMW", "en": "BMW"},
        "Mercedes": {"lv": "Mercedes", "ru": "Mercedes", "en": "Mercedes"},
        "Audi": {"lv": "Audi", "ru": "Audi", "en": "Audi"},
        "Volkswagen": {"lv": "Volkswagen", "ru": "Volkswagen", "en": "Volkswagen"},
        "Skoda": {"lv": "Skoda", "ru": "Skoda", "en": "Skoda"},
    },
}

# ---------------------------------------------------------------------------
# Display order (canonical field names; unlisted fields go last)
# ---------------------------------------------------------------------------

DISPLAY_ORDER: list[str] = [
    spec.canonical_key
    for spec in sorted(CARS_DM_FILTER_REGISTRY, key=lambda x: x.order)
]

# ---------------------------------------------------------------------------
# Units / suffixes
# ---------------------------------------------------------------------------

UNITS: dict[str, str] = {
    "volume_min": "см³",
    "volume_max": "см³",
}

# Cars DM UX has strict canonical set; unknown canonical keys are not rendered.
STRICT_CANONICAL_ONLY = True
