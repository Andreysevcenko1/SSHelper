"""Filter profile for SS.lv transport/cars category.

Defines the canonical field mapping, value normalisation and display order
for car searches on SS.lv.

SS.lv transport/cars filter keys observed in the wild:

  path slug          – make/brand (/transport/cars/{brand}/)
  path slug          – model (/transport/cars/{brand}/{model}/)
  topt[8][min/max]   – price € (Цена / Cena / Price)
  topt[18][min/max]  – year (Год / Gads / Year)
  topt[15][min/max]  – engine volume, litres (Объём / Tilpums / Engine vol)
  opt[34]            – engine/fuel type (Двигатель / Dzinējs / Engine)
  opt[35]            – gearbox (КПП / Ātrumkārba / Gearbox)
  opt[32]            – body type (Кузов / Virsbūve / Body)
  opt[17]            – color (Цвет / Krāsa / Color)
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
    # Keys are real SS.lv option values (opt[34]).
    "engine_type": {
        "493": {"lv": "Benzīns", "ru": "Бензин", "en": "Petrol"},
        "495": {"lv": "Benzīns/gāze", "ru": "Бензин/газ", "en": "Petrol/gas"},
        "494": {"lv": "Dīzelis", "ru": "Дизель", "en": "Diesel"},
        "7434": {"lv": "Hibrīds", "ru": "Гибрид", "en": "Hybrid"},
        "114330": {"lv": "Elektriskais", "ru": "Электро", "en": "Electric"},
    },
    # opt[35]
    "gearbox": {
        "496": {"lv": "Manuāla", "ru": "Механика", "en": "Manual"},
        "497": {"lv": "Automāts", "ru": "Автомат", "en": "Automatic"},
    },
    # opt[32]
    "body_type": {
        "484": {"lv": "Sedans", "ru": "Седан", "en": "Sedan"},
        "483": {"lv": "Universāls", "ru": "Универсал", "en": "Estate"},
        "486": {"lv": "Hečbeks", "ru": "Хэтчбек", "en": "Hatchback"},
        "487": {"lv": "Kupeja", "ru": "Купе", "en": "Coupe"},
        "488": {"lv": "Kabriolets", "ru": "Кабриолет", "en": "Convertible"},
        "476": {"lv": "Minivens", "ru": "Минивэн", "en": "Minivan"},
        "477": {"lv": "Apvidus", "ru": "Внедорожник", "en": "SUV"},
        "114301": {"lv": "Pikaps", "ru": "Пикап", "en": "Pickup"},
        "114384": {"lv": "Mikroautobuss", "ru": "Микроавтобус", "en": "Microbus"},
        "24775": {"lv": "Cits", "ru": "Другой", "en": "Other"},
    },
    # opt[17]
    "color": {
        "6318": {"lv": "Balta", "ru": "Белый", "en": "White"},
        "6319": {"lv": "Brūna", "ru": "Коричневый", "en": "Brown"},
        "6311": {"lv": "Dzeltena", "ru": "Жёлтый", "en": "Yellow"},
        "6313": {"lv": "Gaiši zila", "ru": "Голубой", "en": "Light blue"},
        "153": {"lv": "Melna", "ru": "Чёрный", "en": "Black"},
        "6310": {"lv": "Oranža", "ru": "Оранжевый", "en": "Orange"},
        "6317": {"lv": "Pelēka", "ru": "Серый", "en": "Grey"},
        "6308": {"lv": "Sarkana", "ru": "Красный", "en": "Red"},
        "6316": {"lv": "Sudraba", "ru": "Серебристый", "en": "Silver"},
        "6309": {"lv": "Tumši sarkana", "ru": "Тёмно-красный", "en": "Dark red"},
        "6315": {"lv": "Violeta", "ru": "Фиолетовый", "en": "Purple"},
        "6312": {"lv": "Zaļa", "ru": "Зелёный", "en": "Green"},
        "6314": {"lv": "Zila", "ru": "Синий", "en": "Blue"},
        "137": {"lv": "Cita", "ru": "Другой", "en": "Other"},
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
    "volume_min": "л",
    "volume_max": "л",
}

# Cars DM UX has strict canonical set; unknown canonical keys are not rendered.
STRICT_CANONICAL_ONLY = True
