"""Filter profile for SS.lv real-estate/flats category.

Defines the canonical field mapping, value normalisation and display order
for apartment/flat searches on SS.lv.

SS.lv real-estate filter keys observed in the wild
(confirmed from ss.lv/lv/real-estate/flats/…?topt[…][min]=…):

  topt[18][min/max]  – rooms (Комнаты / Istabas / Rooms)
  topt[15][min/max]  – area m² (Площадь / Platība / Area)
  topt[26][min/max]  – floor (Этаж / Stāvs / Floor)
  topt[27][min/max]  – total floors (Этажей в доме / Stāvi / Floors total)
  opt[17]            – price from (Цена от / Cena no / Price from)
  opt[32]            – price to  (Цена до / Cena līdz / Price to)
  topt[17][min/max]  – price range variant
  opt[1]             – deal type (sell / rent)
  opt[6]             – house type (кирпичный, панельный …)
  pr_min / pr_max    – price range (alternative form)
  mid[…]             – district
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Raw SS.lv key → canonical field name
# ---------------------------------------------------------------------------

RAW_TO_CANONICAL: dict[str, str] = {
    # rooms
    "topt[18][min]": "rooms_min",
    "topt[18][max]": "rooms_max",
    # area m²
    "topt[15][min]": "area_min",
    "topt[15][max]": "area_max",
    # floor (current)
    "topt[26][min]": "floor_min",
    "topt[26][max]": "floor_max",
    # total floors in building
    "topt[27][min]": "floors_total_min",
    "topt[27][max]": "floors_total_max",
    # price – opt single-value form
    "opt[17]": "price_min",
    "opt[32]": "price_max",
    # price – topt range form
    "topt[17][min]": "price_min",
    "topt[17][max]": "price_max",
    # price – plain form
    "pr_min": "price_min",
    "pr_max": "price_max",
    "price_min": "price_min",
    "price_max": "price_max",
    # deal type
    "opt[1]": "deal_type",
    # house type
    "opt[6]": "house_type",
}

# ---------------------------------------------------------------------------
# Human-readable labels per canonical field (i18n key suffix → {lv, ru, en})
# ---------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    "rooms_min": {"lv": "Istabas (no)", "ru": "Комнат (от)", "en": "Rooms (from)"},
    "rooms_max": {"lv": "Istabas (līdz)", "ru": "Комнат (до)", "en": "Rooms (to)"},
    "area_min":  {"lv": "Platība, m² (no)", "ru": "Площадь, м² (от)", "en": "Area, m² (from)"},
    "area_max":  {"lv": "Platība, m² (līdz)", "ru": "Площадь, м² (до)", "en": "Area, m² (to)"},
    "floor_min": {"lv": "Stāvs (no)", "ru": "Этаж (от)", "en": "Floor (from)"},
    "floor_max": {"lv": "Stāvs (līdz)", "ru": "Этаж (до)", "en": "Floor (to)"},
    "floors_total_min": {"lv": "Stāvi (no)", "ru": "Этажей (от)", "en": "Floors total (from)"},
    "floors_total_max": {"lv": "Stāvi (līdz)", "ru": "Этажей (до)", "en": "Floors total (to)"},
    "price_min": {"lv": "Cena no, €", "ru": "Цена от, €", "en": "Price from, €"},
    "price_max": {"lv": "Cena līdz, €", "ru": "Цена до, €", "en": "Price to, €"},
    "deal_type": {"lv": "Darījuma veids", "ru": "Тип сделки", "en": "Deal type"},
    "house_type": {"lv": "Mājas tips", "ru": "Тип дома", "en": "House type"},
}

# ---------------------------------------------------------------------------
# Option value maps: raw value → human-readable label
# ---------------------------------------------------------------------------

OPTION_VALUES: dict[str, dict[str, dict[str, str]]] = {
    "deal_type": {
        "1": {"lv": "Pārdod", "ru": "Продажа", "en": "Sale"},
        "2": {"lv": "Īrē", "ru": "Аренда", "en": "Rent"},
    },
    "house_type": {
        "1":  {"lv": "Ķieģeļu", "ru": "Кирпичный", "en": "Brick"},
        "2":  {"lv": "Paneļu", "ru": "Панельный", "en": "Panel"},
        "3":  {"lv": "Koka", "ru": "Деревянный", "en": "Wood"},
        "4":  {"lv": "Sērijveida", "ru": "Серийный", "en": "Series"},
        "6":  {"lv": "Monolit", "ru": "Монолитный", "en": "Monolith"},
        "7":  {"lv": "Jaunbūve", "ru": "Новостройка", "en": "New build"},
    },
}

# ---------------------------------------------------------------------------
# Display order (canonical field names; unlisted fields go last)
# ---------------------------------------------------------------------------

DISPLAY_ORDER: list[str] = [
    "rooms_min",
    "rooms_max",
    "area_min",
    "area_max",
    "floor_min",
    "floor_max",
    "floors_total_min",
    "floors_total_max",
    "price_min",
    "price_max",
    "deal_type",
    "house_type",
]

# ---------------------------------------------------------------------------
# Units / suffixes
# ---------------------------------------------------------------------------

UNITS: dict[str, str] = {
    "area_min": "м²",
    "area_max": "м²",
}
