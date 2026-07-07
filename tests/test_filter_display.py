"""Personal DM filter display tests: canonical mapping + localized labels."""

import re

import pytest

from app.bot.keyboards.filters import filter_items_kb
from app.services.filters import (
    canonical_filter_key,
    filter_display_label,
    filter_value_label,
    normalize_filter_keys_for_display,
    sanitize_personal_ui_text,
)

_RAW_KEY_PATTERN = re.compile(r"(opt|topt)\[", re.IGNORECASE)


def test_normalize_ss_query_keys_to_canonical():
    raw = {
        "opt[17]": "riga",
        "opt[32]": "mercedes",
        "opt[34]": "e220",
        "opt[35]": "universals",
        "topt[15][min]": "3000",
        "topt[15][max]": "9000",
        "topt[18][min]": "2013",
        "topt[18][max]": "2018",
    }
    normalized = normalize_filter_keys_for_display(raw)
    assert set(normalized.keys()) == {
        "city_district",
        "brand",
        "model",
        "body_type",
        "price_min",
        "price_max",
        "year_min",
        "year_max",
    }


@pytest.mark.parametrize(
    "locale,key,expected",
    [
        ("ru", "opt[17]", "Город/район"),
        ("lv", "opt[17]", "Pilsēta/rajons"),
        ("en", "opt[17]", "City/district"),
        ("ru", "opt[32]", "Марка"),
        ("lv", "opt[34]", "Modelis"),
        ("en", "opt[35]", "Body type"),
        ("ru", "topt[15][min]", "Цена от"),
        ("lv", "topt[15][max]", "Cena līdz"),
        ("en", "topt[18][min]", "Year from"),
        ("ru", "topt[18][max]", "Год до"),
    ],
)
def test_label_resolver_localized_required_keys(locale, key, expected):
    assert filter_display_label(key, locale=locale) == expected


def test_unknown_raw_key_never_displayed_as_raw():
    label = filter_display_label("opt[999]", locale="ru")
    assert label == "Параметр"
    assert not _RAW_KEY_PATTERN.search(label)


def test_unknown_non_raw_key_uses_localized_generic():
    assert filter_display_label("unknown_field", locale="lv") == "Parametrs"


def test_locale_fallback_chain_uses_english_then_generic():
    assert filter_display_label("opt[32]", locale="de") == "Brand"
    assert filter_display_label("unmapped_key", locale="de") == "Parameter"


def test_keyboard_never_contains_raw_ss_keys():
    filters = {
        "opt[17]": "riga",
        "topt[18][min]": "2015",
        "opt[999]": "x",
    }
    kb = filter_items_kb(search_id=1, filters=filters, lang="ru")
    for row in kb.inline_keyboard:
        for button in row:
            text = button.text or ""
            assert not _RAW_KEY_PATTERN.search(text)


def test_canonical_filter_key_mapping_debug_contract():
    assert canonical_filter_key("opt[35]") == "body_type"
    assert canonical_filter_key("topt[15][MAX]") == "price_max"
    assert canonical_filter_key("unknown") is None


def test_cars_profile_mapping_no_semantic_swaps():
    assert filter_display_label("opt[14]", locale="ru", profile="cars") == "Марка"
    assert filter_display_label("opt[15]", locale="ru", profile="cars") == "Модель"
    assert filter_display_label("opt[3]", locale="ru", profile="cars") == "Тип кузова"
    assert filter_display_label("opt[4]", locale="ru", profile="cars") == "Тип топлива"


def test_cars_profile_value_dictionaries_bound_to_correct_fields():
    assert filter_value_label("opt[3]", "2", locale="ru", profile="cars") == "Универсал"
    assert filter_value_label("opt[4]", "2", locale="ru", profile="cars") == "Дизель"
    assert filter_value_label("opt[14]", "BMW", locale="ru", profile="cars") == "BMW"
    assert filter_value_label("opt[15]", "2", locale="ru", profile="cars") == "2"


def test_sanitize_personal_text_replaces_raw_tokens():
    text = "Введите значение для opt[17] и topt[18][min]"
    sanitized = sanitize_personal_ui_text(text, locale="ru", profile="cars")
    assert "opt[" not in sanitized and "topt[" not in sanitized
