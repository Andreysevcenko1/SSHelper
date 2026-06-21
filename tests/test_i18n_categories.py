"""Tests for category i18n — no mixed-language strings, correct locale output."""
import re
import pytest

from app.i18n import SUPPORTED_LANGS, translate_category
from app.services.ss_parser import detect_category, _CATEGORY_MAP

# All canonical category keys produced by detect_category
_ALL_CANONICAL_KEYS = list(_CATEGORY_MAP.values()) + ["ss.lv"]

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

# Russian words that ONLY appear in Russian (not partial matches with lv/en)
_RU_ONLY_WORDS = [
    "Транспорт", "Недвижимость", "Животные", "Электроника",
    "Услуги", "Прочее", "Одежда", "огород", "Еда",
    "Коллекционирование", "быт", "Бизнес", "Спорт",
]

# Latvian-only words (words that only appear in Latvian, not in English or Russian)
_LV_ONLY_WORDS = [
    "Nekustamais", "īpašums", "Dzīvnieki", "Pakalpojumi",
    "Apģērbs", "Dārzs", "Pārtika", "Bizness",
    "Kolekcionēšana", "sadzīve", "Transports",
]

# English-only words (words that only appear in English)
_EN_ONLY_WORDS = [
    "Real estate", "Collectibles", "Household",
    "Animals", "Electronics", "Services", "Clothing",
    "Garden", "Business",
]


# ---------------------------------------------------------------------------
# No Cyrillic in non-Russian output (the core anti-mixing check)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
def test_lv_output_has_no_cyrillic(key):
    result = translate_category(key, "lv")
    assert not _CYRILLIC_RE.search(result), (
        f"translate_category({key!r}, 'lv') = {result!r} contains Cyrillic characters"
    )


@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
def test_en_output_has_no_cyrillic(key):
    result = translate_category(key, "en")
    assert not _CYRILLIC_RE.search(result), (
        f"translate_category({key!r}, 'en') = {result!r} contains Cyrillic characters"
    )


# ---------------------------------------------------------------------------
# Non-Russian output must not contain Russian-only words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
def test_lv_output_has_no_ru_words(key):
    result = translate_category(key, "lv")
    for word in _RU_ONLY_WORDS:
        assert word not in result, (
            f"translate_category({key!r}, 'lv') = {result!r} contains Russian word {word!r}"
        )


@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
def test_en_output_has_no_ru_words(key):
    result = translate_category(key, "en")
    for word in _RU_ONLY_WORDS:
        assert word not in result, (
            f"translate_category({key!r}, 'en') = {result!r} contains Russian word {word!r}"
        )


# ---------------------------------------------------------------------------
# Russian output must not contain Latvian-only words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
def test_ru_output_has_no_lv_only_words(key):
    result = translate_category(key, "ru")
    for word in _LV_ONLY_WORDS:
        assert word not in result, (
            f"translate_category({key!r}, 'ru') = {result!r} contains Latvian word {word!r}"
        )


# ---------------------------------------------------------------------------
# translate_category: specific expected values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,lang,expected", [
    ("transport", "ru", "🚗 Транспорт"),
    ("transport", "lv", "🚗 Transports"),
    ("transport", "en", "🚗 Transport"),
    ("real-estate", "ru", "🏠 Недвижимость"),
    ("real-estate", "lv", "🏠 Nekustamais īpašums"),
    ("real-estate", "en", "🏠 Real estate"),
    ("animals", "ru", "🐾 Животные"),
    ("animals", "lv", "🐾 Dzīvnieki"),
    ("animals", "en", "🐾 Animals"),
    ("electronics", "ru", "💻 Электроника"),
    ("electronics", "lv", "💻 Elektronika"),
    ("electronics", "en", "💻 Electronics"),
    ("services", "ru", "🔧 Услуги"),
    ("services", "lv", "🔧 Pakalpojumi"),
    ("services", "en", "🔧 Services"),
    ("other", "ru", "📦 Прочее"),
    ("other", "lv", "📦 Cits"),
    ("other", "en", "📦 Other"),
    ("clothing", "ru", "👗 Одежда"),
    ("clothing", "lv", "👗 Apģērbs"),
    ("clothing", "en", "👗 Clothing"),
    ("garden", "ru", "🌱 Сад и огород"),
    ("garden", "lv", "🌱 Dārzs"),
    ("garden", "en", "🌱 Garden"),
    ("food", "ru", "🍎 Еда"),
    ("food", "lv", "🍎 Pārtika"),
    ("food", "en", "🍎 Food"),
    ("sport", "ru", "⚽ Спорт"),
    ("sport", "lv", "⚽ Sports"),
    ("sport", "en", "⚽ Sports"),
    ("business", "ru", "💼 Бизнес"),
    ("business", "lv", "💼 Bizness"),
    ("business", "en", "💼 Business"),
    ("collect", "ru", "🏺 Коллекционирование"),
    ("collect", "lv", "🏺 Kolekcionēšana"),
    ("collect", "en", "🏺 Collectibles"),
    ("household", "ru", "🏡 Дом и быт"),
    ("household", "lv", "🏡 Māja un sadzīve"),
    ("household", "en", "🏡 Household"),
    ("ss.lv", "ru", "📋 SS.lv"),
    ("ss.lv", "lv", "📋 SS.lv"),
    ("ss.lv", "en", "📋 SS.lv"),
])
def test_translate_category_exact_values(key, lang, expected):
    assert translate_category(key, lang) == expected


# ---------------------------------------------------------------------------
# translate_category: legacy Russian names (backward compat)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("legacy,lang,expected", [
    ("Транспорт", "ru", "🚗 Транспорт"),
    ("Транспорт", "lv", "🚗 Transports"),
    ("Транспорт", "en", "🚗 Transport"),
    ("Недвижимость", "en", "🏠 Real estate"),
    ("Животные", "lv", "🐾 Dzīvnieki"),
    ("Электроника", "ru", "💻 Электроника"),
    ("Услуги", "lv", "🔧 Pakalpojumi"),
    ("Прочее", "en", "📦 Other"),
    ("Одежда", "lv", "👗 Apģērbs"),
    ("Сад и огород", "en", "🌱 Garden"),
    ("Еда", "lv", "🍎 Pārtika"),
    ("Спорт", "en", "⚽ Sports"),
    ("Бизнес", "lv", "💼 Bizness"),
    ("Коллекционирование", "en", "🏺 Collectibles"),
    ("Дом и быт", "lv", "🏡 Māja un sadzīve"),
    ("SS.lv", "en", "📋 SS.lv"),
])
def test_translate_category_legacy_russian_names(legacy, lang, expected):
    """Old DB records store Russian names; they must be handled without mixing."""
    assert translate_category(legacy, lang) == expected


@pytest.mark.parametrize("legacy", [
    "Транспорт", "Недвижимость", "Животные", "Электроника",
    "Услуги", "Прочее", "Одежда", "Сад и огород", "Еда",
    "Спорт", "Бизнес", "Коллекционирование", "Дом и быт",
])
def test_legacy_lv_output_no_cyrillic(legacy):
    """Legacy Russian key → lv must not produce Cyrillic output."""
    result = translate_category(legacy, "lv")
    assert not _CYRILLIC_RE.search(result), (
        f"translate_category({legacy!r}, 'lv') = {result!r} still contains Cyrillic"
    )


@pytest.mark.parametrize("legacy", [
    "Транспорт", "Недвижимость", "Животные", "Электроника",
    "Услуги", "Прочее", "Одежда", "Сад и огород", "Еда",
    "Спорт", "Бизнес", "Коллекционирование", "Дом и быт",
])
def test_legacy_en_output_no_cyrillic(legacy):
    """Legacy Russian key → en must not produce Cyrillic output."""
    result = translate_category(legacy, "en")
    assert not _CYRILLIC_RE.search(result), (
        f"translate_category({legacy!r}, 'en') = {result!r} still contains Cyrillic"
    )


# ---------------------------------------------------------------------------
# translate_category: unknown key falls back without mixing
# ---------------------------------------------------------------------------

def test_translate_category_unknown_key_shows_raw():
    result = translate_category("some_unknown_category", "lv")
    assert "some_unknown_category" in result
    assert not _CYRILLIC_RE.search(result)


def test_translate_category_unknown_key_same_for_all_langs():
    """Unknown key produces the same raw name regardless of lang."""
    key = "mystery_category"
    results = {lang: translate_category(key, lang) for lang in SUPPORTED_LANGS}
    names = [r.split(" ", 1)[1] for r in results.values()]  # strip icon
    assert len(set(names)) == 1, f"Different outputs for unknown key: {results}"


# ---------------------------------------------------------------------------
# detect_category returns canonical (non-Russian, ASCII) keys
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected_key", [
    ("https://www.ss.lv/lv/transport/cars/", "transport"),
    ("https://www.ss.lv/lv/real-estate/flats/riga/", "real-estate"),
    ("https://www.ss.lv/lv/animals/dogs/", "animals"),
    ("https://www.ss.lv/lv/electronics/phones/", "electronics"),
    ("https://www.ss.lv/lv/services/", "services"),
    ("https://www.ss.lv/lv/other/", "other"),
    ("https://www.ss.lv/lv/clothing/", "clothing"),
    ("https://www.ss.lv/lv/garden/", "garden"),
    ("https://www.ss.lv/lv/food/", "food"),
    ("https://www.ss.lv/lv/sport/fitness/", "sport"),
    ("https://www.ss.lv/lv/business/", "business"),
    ("https://www.ss.lv/lv/household/furniture/", "household"),
    ("https://www.ss.lv/lv/collect/", "collect"),
    ("https://www.ss.lv/", "ss.lv"),
])
def test_detect_category_returns_canonical_key(url, expected_key):
    assert detect_category(url) == expected_key


def test_detect_category_key_is_ascii():
    """Canonical keys must be ASCII (no Cyrillic, no mixed language)."""
    for url in [
        "https://www.ss.lv/lv/transport/cars/",
        "https://www.ss.lv/lv/real-estate/",
        "https://www.ss.lv/lv/animals/",
        "https://www.ss.lv/lv/electronics/",
        "https://www.ss.lv/",
    ]:
        key = detect_category(url)
        assert key.isascii(), f"detect_category({url!r}) returned non-ASCII key {key!r}"


# ---------------------------------------------------------------------------
# All langs produce a non-empty result with an emoji icon
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", _ALL_CANONICAL_KEYS)
@pytest.mark.parametrize("lang", SUPPORTED_LANGS)
def test_translate_category_returns_nonempty_with_icon(key, lang):
    result = translate_category(key, lang)
    assert result.strip(), f"Empty result for ({key!r}, {lang!r})"
    # First character should be an emoji (non-ASCII)
    assert not result[0].isascii(), (
        f"Expected emoji icon at start, got: {result!r}"
    )
