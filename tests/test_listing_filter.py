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


# ---------------------------------------------------------------------------
# Buy-request detection
# ---------------------------------------------------------------------------


class TestIsBuyRequest:
    def test_perkam_lv(self):
        from app.services.listing_filter import is_buy_request
        listing = _listing(title="Pērkam. покупаем. Visu marku auto jebkurā stāvoklī")
        assert is_buy_request(listing) is True

    def test_kuplyu_ru(self):
        from app.services.listing_filter import is_buy_request
        listing = _listing(title="Куплю авто в любом состоянии, срочный выкуп")
        assert is_buy_request(listing) is True

    def test_vykup(self):
        from app.services.listing_filter import is_buy_request
        listing = _listing(title="Выкуп автомобилей")
        assert is_buy_request(listing) is True

    def test_normal_sale_not_flagged(self):
        from app.services.listing_filter import is_buy_request
        listing = _listing(title="BMW X5 3.0d, 2018, ļoti labā stāvoklī")
        assert is_buy_request(listing) is False

    def test_normal_flat_not_flagged(self):
        from app.services.listing_filter import is_buy_request
        listing = _listing(title="Izīrē 2-istabu dzīvokli centrā")
        assert is_buy_request(listing) is False


# ---------------------------------------------------------------------------
# Flats numeric + series filters
# ---------------------------------------------------------------------------


class TestFlatsFilters:
    def test_price_min_drops_cheaper_flat(self):
        listing = _listing(price_total_eur=300.0)
        ok, reason = listing_matches_filters(listing, {"topt[8][min]": "500"}, "flats")
        assert ok is False
        assert "price_min" in reason

    def test_rooms_min(self):
        listing = _listing(rooms=1)
        ok, reason = listing_matches_filters(listing, {"topt[1][min]": "2"}, "flats")
        assert ok is False
        assert "rooms_min" in reason

    def test_area_range_pass(self):
        listing = _listing(area_m2=55.0)
        ok, _ = listing_matches_filters(
            listing, {"topt[3][min]": "40", "topt[3][max]": "80"}, "flats"
        )
        assert ok is True

    def test_floor_max(self):
        listing = _listing(floor_current=9)
        ok, reason = listing_matches_filters(listing, {"topt[4][max]": "5"}, "flats")
        assert ok is False
        assert "floor_max" in reason

    def test_series_match(self):
        listing = _listing(series="Hrušč.")
        ok, _ = listing_matches_filters(listing, {"opt[6]": "76"}, "flats")
        assert ok is True

    def test_series_mismatch(self):
        listing = _listing(series="Jaun.")
        ok, reason = listing_matches_filters(listing, {"opt[6]": "76"}, "flats")
        assert ok is False
        assert "series" in reason

    def test_missing_data_never_drops(self):
        listing = _listing()
        ok, _ = listing_matches_filters(
            listing,
            {"topt[8][min]": "500", "topt[1][min]": "2", "opt[6]": "76"},
            "flats",
        )
        assert ok is True
