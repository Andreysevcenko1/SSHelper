"""Tests for category-specific filter profiles, renderer, and profile detection.

Acceptance criteria:
- flats and cars profiles correctly map raw SS.lv keys to canonical fields.
- Range formatting renders correctly per profile.
- Unknown raw keys do NOT appear in UI output (no opt[/topt[).
- Renderer output never contains raw SS.lv key patterns.
- Profile detection works for flats and cars URLs.
- Backward compatibility: unknown profile falls back to generic renderer (no raw keys).
"""

import re

import pytest

from app.filters.profiles import detect_profile, get_profile, to_canonical
from app.filters.renderer import render_canonical_filters

_RAW_KEY_RE = re.compile(r"(opt|topt|mid)\[", re.IGNORECASE)


# ---------------------------------------------------------------------------
# detect_profile
# ---------------------------------------------------------------------------


class TestDetectProfile:
    def test_flats_url(self):
        url = "https://www.ss.lv/lv/real-estate/flats/riga/sell/?topt[18][min]=2"
        assert detect_profile(url) == "flats"

    def test_cars_url(self):
        url = "https://www.ss.lv/lv/transport/cars/?topt[8][min]=2015"
        assert detect_profile(url) == "cars"

    def test_unknown_category(self):
        url = "https://www.ss.lv/lv/services/"
        assert detect_profile(url) is None

    def test_electronics_url_unknown(self):
        url = "https://www.ss.lv/lv/electronics/computers/"
        assert detect_profile(url) is None

    def test_empty_url(self):
        assert detect_profile("") is None

    def test_flats_with_subdirectory(self):
        url = "https://ss.lv/lv/real-estate/flats/riga/center/hand_over/"
        assert detect_profile(url) == "flats"

    def test_cars_with_filter_params(self):
        url = "https://ss.lv/lv/transport/cars/bmw/?opt[4]=2&topt[8][min]=2018"
        assert detect_profile(url) == "cars"

    def test_flats_without_trailing_slash(self):
        url = "https://ss.lv/lv/real-estate/flats"
        assert detect_profile(url) == "flats"

    def test_cars_without_trailing_slash(self):
        url = "https://ss.lv/lv/transport/cars"
        assert detect_profile(url) == "cars"


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_flats(self):
        assert get_profile("flats") is not None

    def test_cars(self):
        assert get_profile("cars") is not None

    def test_unknown(self):
        assert get_profile("unknown") is None

    def test_none(self):
        assert get_profile(None) is None


# ---------------------------------------------------------------------------
# to_canonical – flats
# ---------------------------------------------------------------------------


class TestToCanonicalFlats:
    def test_rooms_min(self):
        result = to_canonical({"topt[18][min]": "2"}, "flats")
        assert result["rooms_min"] == "2"

    def test_rooms_max(self):
        result = to_canonical({"topt[18][max]": "4"}, "flats")
        assert result["rooms_max"] == "4"

    def test_area_range(self):
        result = to_canonical({"topt[15][min]": "45", "topt[15][max]": "80"}, "flats")
        assert result["area_min"] == "45"
        assert result["area_max"] == "80"

    def test_price_opt_form(self):
        result = to_canonical({"opt[17]": "50000", "opt[32]": "120000"}, "flats")
        assert result["price_min"] == "50000"
        assert result["price_max"] == "120000"

    def test_price_pr_form(self):
        result = to_canonical({"pr_min": "30000", "pr_max": "90000"}, "flats")
        assert result["price_min"] == "30000"
        assert result["price_max"] == "90000"

    def test_unknown_key_dropped(self):
        result = to_canonical({"topt[99][min]": "5"}, "flats")
        assert result == {}

    def test_deal_type(self):
        result = to_canonical({"opt[1]": "1"}, "flats")
        assert result["deal_type"] == "1"

    def test_house_type(self):
        result = to_canonical({"opt[6]": "1"}, "flats")
        assert result["house_type"] == "1"

    def test_floor(self):
        result = to_canonical({"topt[26][min]": "2", "topt[26][max]": "10"}, "flats")
        assert result["floor_min"] == "2"
        assert result["floor_max"] == "10"


# ---------------------------------------------------------------------------
# to_canonical – cars
# ---------------------------------------------------------------------------


class TestToCanonicalCars:
    def test_year_range(self):
        result = to_canonical({"topt[8][min]": "2018", "topt[8][max]": "2023"}, "cars")
        assert result["year_min"] == "2018"
        assert result["year_max"] == "2023"

    def test_mileage(self):
        result = to_canonical({"topt[10][max]": "120000"}, "cars")
        assert result["mileage_max"] == "120000"

    def test_engine(self):
        result = to_canonical({"topt[11][min]": "1600", "topt[11][max]": "2000"}, "cars")
        assert result["engine_min"] == "1600"
        assert result["engine_max"] == "2000"

    def test_fuel(self):
        result = to_canonical({"opt[4]": "2"}, "cars")
        assert result["fuel"] == "2"

    def test_gearbox(self):
        result = to_canonical({"opt[5]": "2"}, "cars")
        assert result["gearbox"] == "2"

    def test_body_type(self):
        result = to_canonical({"opt[3]": "7"}, "cars")
        assert result["body_type"] == "7"

    def test_price_range(self):
        result = to_canonical({"topt[17][min]": "10000", "topt[17][max]": "15000"}, "cars")
        assert result["price_min"] == "10000"
        assert result["price_max"] == "15000"

    def test_unknown_key_dropped(self):
        result = to_canonical({"opt[999]": "1"}, "cars")
        assert result == {}


# ---------------------------------------------------------------------------
# render_canonical_filters – no raw keys in output
# ---------------------------------------------------------------------------


def _assert_no_raw_keys(lines: list[str]) -> None:
    for line in lines:
        assert not _RAW_KEY_RE.search(line), (
            f"Raw SS.lv key pattern found in rendered line: {line!r}"
        )


class TestRenderFlats:
    def test_rooms_range_rendered(self):
        raw = {"topt[18][min]": "2", "topt[18][max]": "3"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        assert any("2" in l for l in lines)
        assert any("3" in l for l in lines)
        _assert_no_raw_keys(lines)

    def test_area_with_unit(self):
        raw = {"topt[15][min]": "45", "topt[15][max]": "80"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " ".join(lines)
        assert "м²" in joined
        _assert_no_raw_keys(lines)

    def test_price_label_ru(self):
        raw = {"pr_min": "50000", "pr_max": "120000"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " ".join(lines)
        assert "Цена" in joined
        _assert_no_raw_keys(lines)

    def test_deal_type_resolved(self):
        raw = {"opt[1]": "1"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " ".join(lines)
        assert "Продажа" in joined
        _assert_no_raw_keys(lines)

    def test_house_type_resolved(self):
        raw = {"opt[6]": "1"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " ".join(lines)
        assert "Кирпичный" in joined
        _assert_no_raw_keys(lines)

    def test_unknown_raw_key_not_in_output(self):
        raw = {"topt[99][min]": "5", "topt[18][min]": "2"}
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " ".join(lines)
        # unknown key value "5" should not appear, but known "2" should
        assert "2" in joined
        assert "99" not in joined
        _assert_no_raw_keys(lines)

    def test_display_order_rooms_before_price(self):
        raw = {
            "pr_min": "50000",
            "topt[18][min]": "2",
        }
        lines = render_canonical_filters(raw, "flats", locale="ru")
        joined = " | ".join(lines)
        rooms_pos = joined.find("Комнат")
        price_pos = joined.find("Цена")
        assert rooms_pos < price_pos, "Rooms should appear before price"

    def test_label_lv(self):
        raw = {"topt[18][min]": "2"}
        lines = render_canonical_filters(raw, "flats", locale="lv")
        joined = " ".join(lines)
        assert "Istabas" in joined

    def test_label_en(self):
        raw = {"topt[18][min]": "2"}
        lines = render_canonical_filters(raw, "flats", locale="en")
        joined = " ".join(lines)
        assert "Rooms" in joined


class TestRenderCars:
    def test_year_rendered(self):
        raw = {"topt[8][min]": "2018"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "2018" in joined
        assert "Год" in joined
        _assert_no_raw_keys(lines)

    def test_mileage_with_unit(self):
        raw = {"topt[10][max]": "120000"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "км" in joined
        _assert_no_raw_keys(lines)

    def test_fuel_resolved(self):
        raw = {"opt[4]": "2"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "Дизель" in joined
        _assert_no_raw_keys(lines)

    def test_gearbox_resolved(self):
        raw = {"opt[5]": "2"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "Автомат" in joined
        _assert_no_raw_keys(lines)

    def test_price_label_ru(self):
        raw = {"topt[17][min]": "10000", "topt[17][max]": "15000"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "Цена" in joined
        _assert_no_raw_keys(lines)

    def test_unknown_raw_key_not_in_output(self):
        raw = {"opt[999]": "1", "opt[4]": "1"}
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " ".join(lines)
        assert "999" not in joined
        _assert_no_raw_keys(lines)

    def test_display_order_make_before_price(self):
        raw = {
            "pr_min": "10000",
            "opt[14]": "BMW",
        }
        lines = render_canonical_filters(raw, "cars", locale="ru")
        joined = " | ".join(lines)
        make_pos = joined.find("Марка")
        price_pos = joined.find("Цена")
        assert make_pos < price_pos, "Make should appear before price"

    def test_label_lv(self):
        raw = {"opt[4]": "1"}
        lines = render_canonical_filters(raw, "cars", locale="lv")
        joined = " ".join(lines)
        assert "Degviela" in joined

    def test_label_en(self):
        raw = {"opt[5]": "1"}
        lines = render_canonical_filters(raw, "cars", locale="en")
        joined = " ".join(lines)
        assert "Gearbox" in joined


# ---------------------------------------------------------------------------
# Generic fallback (unknown profile) – still no raw keys
# ---------------------------------------------------------------------------


class TestRenderGeneric:
    def test_no_raw_keys_in_output(self):
        raw = {
            "opt[123]": "456",
            "topt[789][min]": "10",
            "topt[789][max]": "50",
            "mid[11]": "12",
            "pr_min": "5000",
            "pr_max": "15000",
        }
        lines = render_canonical_filters(raw, profile_name=None, locale="ru")
        _assert_no_raw_keys(lines)

    def test_plain_keys_still_shown(self):
        raw = {"pr_min": "1000", "pr_max": "9000"}
        lines = render_canonical_filters(raw, profile_name=None, locale="ru")
        joined = " ".join(lines)
        # price keys are clean and should appear
        assert "1000" in joined or "9000" in joined


# ---------------------------------------------------------------------------
# Regression: apartment URL renders apartment-specific fields only
# ---------------------------------------------------------------------------


class TestRegressionFlatsUrl:
    """Full regression: flats URL → profile detected → correct rendering."""

    def test_profile_detected(self):
        url = "https://www.ss.lv/lv/real-estate/flats/riga/sell/"
        assert detect_profile(url) == "flats"

    def test_rendering_no_raw_keys(self):
        raw = {
            "topt[18][min]": "2",
            "topt[15][max]": "80",
            "pr_max": "150000",
            "opt[6]": "1",
        }
        lines = render_canonical_filters(raw, "flats", locale="ru")
        _assert_no_raw_keys(lines)
        joined = " ".join(lines)
        assert "Комнат" in joined
        assert "Площадь" in joined
        assert "Цена" in joined
        assert "Кирпичный" in joined


# ---------------------------------------------------------------------------
# Regression: cars URL renders cars-specific fields only
# ---------------------------------------------------------------------------


class TestRegressionCarsUrl:
    def test_profile_detected(self):
        url = "https://www.ss.lv/lv/transport/cars/bmw/"
        assert detect_profile(url) == "cars"

    def test_rendering_no_raw_keys(self):
        raw = {
            "topt[8][min]": "2015",
            "topt[10][max]": "200000",
            "opt[4]": "2",
            "opt[5]": "2",
            "pr_min": "5000",
            "pr_max": "20000",
        }
        lines = render_canonical_filters(raw, "cars", locale="ru")
        _assert_no_raw_keys(lines)
        joined = " ".join(lines)
        assert "Год" in joined
        assert "Пробег" in joined
        assert "Дизель" in joined
        assert "Автомат" in joined
        assert "Цена" in joined
