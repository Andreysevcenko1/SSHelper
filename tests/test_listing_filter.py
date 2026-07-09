"""Tests for local (client-side) listing filter matching."""

from app.services.listing_filter import listing_matches_filters
from app.services.ss_parser import Listing


def _listing(**kw) -> Listing:
    base = dict(external_id="1", title="BMW 320", url="https://www.ss.lv/msg/x.html")
    base.update(kw)
    return Listing(**base)


def test_no_filters_always_match():
    ok, reason = listing_matches_filters(_listing(), {}, "cars")
    assert ok and reason is None


def test_price_min_filters_out_cheap_listing():
    lst = _listing(price="3,500 €", price_total_eur=3500.0)
    ok, reason = listing_matches_filters(lst, {"topt[8][min]": "5000"}, "cars")
    assert not ok
    assert "price_min" in reason


def test_price_min_passes_expensive_listing():
    lst = _listing(price_total_eur=12000.0)
    ok, _ = listing_matches_filters(lst, {"topt[8][min]": "5000"}, "cars")
    assert ok


def test_price_max_filters_out_expensive_listing():
    lst = _listing(price_total_eur=25000.0)
    ok, reason = listing_matches_filters(lst, {"topt[8][max]": "10000"}, "cars")
    assert not ok and "price_max" in reason


def test_price_parsed_from_string_when_no_total():
    lst = _listing(price="4,200 €")
    ok, _ = listing_matches_filters(lst, {"topt[8][min]": "5000"}, "cars")
    assert not ok


def test_missing_price_never_drops_listing():
    lst = _listing(price=None)
    ok, _ = listing_matches_filters(lst, {"topt[8][min]": "5000"}, "cars")
    assert ok


def test_year_range():
    lst = _listing(car_year="2015. gads")
    assert listing_matches_filters(lst, {"topt[18][min]": "2018"}, "cars")[0] is False
    assert listing_matches_filters(lst, {"topt[18][min]": "2010"}, "cars")[0] is True
    assert listing_matches_filters(lst, {"topt[18][max]": "2012"}, "cars")[0] is False


def test_volume_range():
    lst = _listing(car_engine="2.0 dīzelis")
    assert listing_matches_filters(lst, {"topt[15][min]": "3.0"}, "cars")[0] is False
    assert listing_matches_filters(lst, {"topt[15][max]": "2.5"}, "cars")[0] is True


def test_engine_type_select_match():
    lst = _listing(car_engine="2.0 dīzelis")
    # 494 = Diesel
    assert listing_matches_filters(lst, {"opt[34]": "494"}, "cars")[0] is True
    # 493 = Petrol
    ok, reason = listing_matches_filters(lst, {"opt[34]": "493"}, "cars")
    assert ok is False and "engine_type" in reason


def test_gearbox_select_match():
    lst = _listing(car_gearbox="Automāts")
    assert listing_matches_filters(lst, {"opt[35]": "497"}, "cars")[0] is True
    assert listing_matches_filters(lst, {"opt[35]": "496"}, "cars")[0] is False


def test_select_missing_listing_data_passes():
    lst = _listing(car_gearbox=None)
    assert listing_matches_filters(lst, {"opt[35]": "497"}, "cars")[0] is True


def test_unknown_filter_keys_ignored():
    lst = _listing(price_total_eur=100.0)
    assert listing_matches_filters(lst, {"opt[999]": "zzz"}, "cars")[0] is True


def test_no_profile_always_matches():
    lst = _listing(price_total_eur=1.0)
    assert listing_matches_filters(lst, {"topt[8][min]": "5000"}, None)[0] is True
