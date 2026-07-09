"""Filter profile for SS.lv real-estate/flats category.

Defines the canonical field mapping, value normalisation and display order
for apartment/flat searches on SS.lv.

Real SS.lv flats filter schema (probed live at
https://www.ss.lv/lv/real-estate/flats/riga/centre/):

  topt[8][min/max]   – price € (Cena / Цена)
  topt[1][min/max]   – rooms (Istabas / Комнаты)
  topt[3][min/max]   – area m² (Platība / Площадь)
  topt[4][min/max]   – floor (Stāvs / Этаж)
  opt[6]             – house series (Sērija: 103., Hrušč., Staļina, Jaun. …)
  opt[11]            – street (Iela; options come from the page schema)
  sid                – deal type, applied via URL PATH (…/sell/, /hand_over/ …)

City / district / deal type are URL path segments and come from the saved
search URL itself, not from query params.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Raw SS.lv key → canonical field name
# ---------------------------------------------------------------------------

RAW_TO_CANONICAL: dict[str, str] = {
    # price (real schema)
    "topt[8][min]": "price_min",
    "topt[8][max]": "price_max",
    # rooms (real schema)
    "topt[1][min]": "rooms_min",
    "topt[1][max]": "rooms_max",
    # area m² (real schema)
    "topt[3][min]": "area_min",
    "topt[3][max]": "area_max",
    # floor (real schema)
    "topt[4][min]": "floor_min",
    "topt[4][max]": "floor_max",
    # house series (real schema)
    "opt[6]": "series",
    # street (real schema; option labels come from page schema)
    "opt[11]": "street",
    # deal type is a URL path segment on SS.lv; kept for saved-value rendering
    "sid": "deal_type",
    # ---- legacy aliases (older saved searches) ----
    "topt[18][min]": "rooms_min",
    "topt[18][max]": "rooms_max",
    "topt[15][min]": "area_min",
    "topt[15][max]": "area_max",
    "topt[26][min]": "floor_min",
    "topt[26][max]": "floor_max",
    "topt[17][min]": "price_min",
    "topt[17][max]": "price_max",
    "opt[17]": "price_min",
    "opt[32]": "price_max",
    "opt[1]": "deal_type",
    "pr_min": "price_min",
    "pr_max": "price_max",
    "price_min": "price_min",
    "price_max": "price_max",
}

# ---------------------------------------------------------------------------
# Human-readable labels per canonical field (i18n key suffix → {lv, ru, en})
# ---------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    "price_min": {"lv": "Cena no, €", "ru": "Цена от, €", "en": "Price from, €"},
    "price_max": {"lv": "Cena līdz, €", "ru": "Цена до, €", "en": "Price to, €"},
    "rooms_min": {"lv": "Istabas (no)", "ru": "Комнат (от)", "en": "Rooms (from)"},
    "rooms_max": {"lv": "Istabas (līdz)", "ru": "Комнат (до)", "en": "Rooms (to)"},
    "area_min":  {"lv": "Platība, m² (no)", "ru": "Площадь, м² (от)", "en": "Area, m² (from)"},
    "area_max":  {"lv": "Platība, m² (līdz)", "ru": "Площадь, м² (до)", "en": "Area, m² (to)"},
    "floor_min": {"lv": "Stāvs (no)", "ru": "Этаж (от)", "en": "Floor (from)"},
    "floor_max": {"lv": "Stāvs (līdz)", "ru": "Этаж (до)", "en": "Floor (to)"},
    "series":    {"lv": "Sērija", "ru": "Серия", "en": "Series"},
    "street":    {"lv": "Iela", "ru": "Улица", "en": "Street"},
    "deal_type": {"lv": "Darījuma veids", "ru": "Тип сделки", "en": "Deal type"},
}

# ---------------------------------------------------------------------------
# Option value maps: raw value → human-readable label
# ---------------------------------------------------------------------------

OPTION_VALUES: dict[str, dict[str, dict[str, str]]] = {
    "series": {
        "67":   {"lv": "103.", "ru": "103.", "en": "103."},
        "68":   {"lv": "104.", "ru": "104.", "en": "104."},
        "70":   {"lv": "467.", "ru": "467.", "en": "467."},
        "73":   {"lv": "Čehu pr.", "ru": "Чешский пр.", "en": "Czech pr."},
        "76":   {"lv": "Hrušč.", "ru": "Хрущёвка", "en": "Khrushchev"},
        "74":   {"lv": "M. ģim.", "ru": "Малосемейка", "en": "Small fam."},
        "79":   {"lv": "P. kara", "ru": "Довоенный", "en": "Pre-war"},
        "77":   {"lv": "Priv. m.", "ru": "Частный дом", "en": "Private house"},
        "3616": {"lv": "Renov.", "ru": "Реновир.", "en": "Renovated"},
        "78":   {"lv": "Specpr.", "ru": "Спецпроект", "en": "Spec. project"},
        "75":   {"lv": "Staļina", "ru": "Сталинка", "en": "Stalin-era"},
        "3596": {"lv": "Jaun.", "ru": "Новостройка", "en": "New build"},
    },
    "deal_type": {
        "sell": {"lv": "Pārdod", "ru": "Продажа", "en": "Sale"},
        "hand_over": {"lv": "Izīrē", "ru": "Сдают", "en": "For rent"},
        "buy": {"lv": "Pērk", "ru": "Покупка", "en": "Buying"},
        "remove": {"lv": "Īrē", "ru": "Снимут", "en": "Renting"},
        "change": {"lv": "Maina", "ru": "Обмен", "en": "Exchange"},
        # legacy numeric values
        "1": {"lv": "Pārdod", "ru": "Продажа", "en": "Sale"},
        "2": {"lv": "Īrē", "ru": "Аренда", "en": "Rent"},
    },
}

# ---------------------------------------------------------------------------
# Display order (canonical field names; unlisted fields go last)
# ---------------------------------------------------------------------------

DISPLAY_ORDER: list[str] = [
    "deal_type",
    "price_min",
    "price_max",
    "rooms_min",
    "rooms_max",
    "area_min",
    "area_max",
    "floor_min",
    "floor_max",
    "series",
    "street",
]

# ---------------------------------------------------------------------------
# Units / suffixes
# ---------------------------------------------------------------------------

UNITS: dict[str, str] = {
    "area_min": "м²",
    "area_max": "м²",
    "price_min": "€",
    "price_max": "€",
}
