"""Tests for URL validation and filter CRUD logic."""
import pytest

from app.services.filters import (
    base_url_without_query,
    build_effective_url,
    canonical_filter_key,
    extract_filters_from_url,
    filters_from_json,
    filters_to_json,
    normalize_filter_keys_for_display,
    normalize_filters,
)


# ------------------------------------------------------------------ #
# URL parsing                                                          #
# ------------------------------------------------------------------ #


def test_extract_filters_empty_query():
    filters = extract_filters_from_url("https://www.ss.lv/lv/transport/cars/")
    assert filters == {}


def test_extract_filters_single_param():
    filters = extract_filters_from_url("https://www.ss.lv/lv/transport/cars/?pr_min=5000")
    assert filters == {"pr_min": "5000"}


def test_extract_filters_multiple_params():
    filters = extract_filters_from_url(
        "https://www.ss.lv/lv/transport/cars/?pr_min=5000&pr_max=15000"
    )
    assert filters["pr_min"] == "5000"
    assert filters["pr_max"] == "15000"


def test_base_url_strips_query():
    url = "https://www.ss.lv/lv/transport/cars/?pr_min=5000&pr_max=15000"
    assert base_url_without_query(url) == "https://www.ss.lv/lv/transport/cars/"


def test_build_effective_url_roundtrip():
    base = "https://www.ss.lv/lv/transport/cars/"
    filters = {"pr_min": "5000", "pr_max": "15000"}
    effective = build_effective_url(base, filters)
    assert "pr_min=5000" in effective
    assert "pr_max=15000" in effective
    assert effective.startswith(base)


# ------------------------------------------------------------------ #
# Filter normalisation                                                 #
# ------------------------------------------------------------------ #


def test_normalize_filters_sorts_keys():
    raw = {"z_key": "1", "a_key": "2"}
    result = normalize_filters(raw)
    assert list(result.keys()) == ["a_key", "z_key"]


def test_normalize_filters_strips_whitespace():
    raw = {" key ": " value "}
    result = normalize_filters(raw)
    assert "key" in result
    assert result["key"] == "value"


def test_normalize_filters_drops_empty():
    raw = {"key": "", "good": "val"}
    result = normalize_filters(raw)
    assert "key" not in result
    assert result["good"] == "val"


def test_normalize_filter_keys_for_display_known_ss_keys():
    raw = {"opt[17]": "riga", "topt[15][min]": "1000", "topt[18][max]": "2020"}
    normalized = normalize_filter_keys_for_display(raw)
    assert normalized == {"city_district": "riga", "price_min": "1000", "year_max": "2020"}


def test_canonical_filter_key_is_case_insensitive():
    assert canonical_filter_key("topt[15][MAX]") == "price_max"


# ------------------------------------------------------------------ #
# JSON serialisation                                                   #
# ------------------------------------------------------------------ #


def test_filters_to_json_empty():
    assert filters_to_json({}) is None


def test_filters_to_json_roundtrip():
    filters = {"pr_min": "5000", "pr_max": "15000"}
    json_str = filters_to_json(filters)
    assert json_str is not None
    restored = filters_from_json(json_str)
    assert restored == filters


def test_filters_from_json_none():
    assert filters_from_json(None) == {}


def test_filters_from_json_invalid():
    assert filters_from_json("not-json") == {}


# ------------------------------------------------------------------ #
# URL validation (inline replication of the add_search logic)         #
# ------------------------------------------------------------------ #


from urllib.parse import urlparse


def _validate_ss_url(url: str) -> str | None:
    url = url.strip()
    if not url:
        return "URL не может быть пустым."
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "URL должен начинаться с http:// или https://"
    if not parsed.netloc or "ss.lv" not in parsed.netloc:
        return "URL должен быть с домена ss.lv"
    return None


@pytest.mark.parametrize("url", [
    "https://www.ss.lv/lv/transport/cars/",
    "http://ss.lv/lv/real-estate/flats/riga/",
    "https://ss.lv/lv/transport/cars/?pr_min=5000",
])
def test_valid_ss_urls(url):
    assert _validate_ss_url(url) is None


@pytest.mark.parametrize("url,expected_fragment", [
    ("", "пустым"),
    ("ftp://ss.lv/foo", "http"),
    ("https://example.com/path", "ss.lv"),
    ("not-a-url", "http"),
])
def test_invalid_ss_urls(url, expected_fragment):
    error = _validate_ss_url(url)
    assert error is not None
    assert expected_fragment in error


# ------------------------------------------------------------------ #
# filter_cmds helpers                                                  #
# ------------------------------------------------------------------ #


def test_sorted_fields_consistency():
    """_sorted_fields should produce deterministic ordered tuples."""
    from app.bot.handlers.filter_cmds import _sorted_fields

    schema = {
        "z_field": {"label": "Z Label", "type": "text", "options": []},
        "a_field": {"label": "A Label", "type": "select", "options": []},
    }
    fields = _sorted_fields(schema)
    names = [f[1] for f in fields]
    assert names == sorted(names)


def test_field_by_idx():
    from app.bot.handlers.filter_cmds import _field_by_idx

    schema = {"a": {"label": "A"}, "b": {"label": "B"}}
    field_order = ["a", "b"]
    name, info = _field_by_idx(schema, field_order, 0)
    assert name == "a"
    assert info["label"] == "A"

    name2, info2 = _field_by_idx(schema, field_order, 1)
    assert name2 == "b"

    none_name, none_info = _field_by_idx(schema, field_order, 99)
    assert none_name is None
    assert none_info is None
