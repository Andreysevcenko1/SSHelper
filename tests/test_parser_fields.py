"""Tests for the real-estate field extraction helpers in ss_parser."""

import pytest
from bs4 import BeautifulSoup

from app.services.ss_parser import (
    Listing,
    SSParser,
    _parse_location,
    _parse_price_fields,
    _parse_realestate_cells,
    _try_parse_area,
    _try_parse_floor,
    _try_parse_rooms,
    enrich_listing_from_detail,
    normalize_price_eur,
    parse_detail_page,
)


# ---------------------------------------------------------------------------
# _try_parse_rooms
# ---------------------------------------------------------------------------

class TestTryParseRooms:
    def test_single_digit(self):
        assert _try_parse_rooms("3") == 3

    def test_two_digits(self):
        assert _try_parse_rooms("10") == 10

    def test_whitespace(self):
        assert _try_parse_rooms("  5  ") == 5

    def test_zero_rejected(self):
        assert _try_parse_rooms("0") is None

    def test_too_large_rejected(self):
        assert _try_parse_rooms("21") is None

    def test_non_numeric(self):
        assert _try_parse_rooms("abc") is None

    def test_decimal_rejected(self):
        assert _try_parse_rooms("3.5") is None


# ---------------------------------------------------------------------------
# _try_parse_area
# ---------------------------------------------------------------------------

class TestTryParseArea:
    def test_integer_area(self):
        assert _try_parse_area("68") == 68.0

    def test_decimal_dot(self):
        assert _try_parse_area("68.5") == 68.5

    def test_decimal_comma(self):
        assert _try_parse_area("68,5") == 68.5

    def test_with_m2_suffix(self):
        assert _try_parse_area("68.5 m²") == 68.5

    def test_too_small_rejected(self):
        assert _try_parse_area("4") is None

    def test_too_large_rejected(self):
        assert _try_parse_area("2001") is None

    def test_non_numeric(self):
        assert _try_parse_area("abc") is None


# ---------------------------------------------------------------------------
# _try_parse_floor
# ---------------------------------------------------------------------------

class TestTryParseFloor:
    def test_normal(self):
        assert _try_parse_floor("3/9") == (3, 9)

    def test_with_whitespace(self):
        assert _try_parse_floor(" 5 / 12 ") == (5, 12)

    def test_single_digit(self):
        assert _try_parse_floor("1/1") == (1, 1)

    def test_invalid_no_slash(self):
        assert _try_parse_floor("3") is None

    def test_invalid_text(self):
        assert _try_parse_floor("abc/def") is None


# ---------------------------------------------------------------------------
# normalize_price_eur (parser module)
# ---------------------------------------------------------------------------

class TestNormalizePriceEurParser:
    def test_plain(self):
        assert normalize_price_eur("125000") == 125000.0

    def test_with_spaces_and_euro(self):
        assert normalize_price_eur("125 000 €") == 125000.0

    def test_nbsp(self):
        assert normalize_price_eur("125\u00a0000\u00a0€") == 125000.0

    def test_none(self):
        assert normalize_price_eur(None) is None

    def test_empty(self):
        assert normalize_price_eur("") is None


# ---------------------------------------------------------------------------
# _parse_price_fields
# ---------------------------------------------------------------------------

class TestParsePriceFields:
    def test_sell_total(self):
        total, monthly, per_m2 = _parse_price_fields("125 000 €", "sell", None)
        assert total == 125000.0
        assert monthly is None
        assert per_m2 is None

    def test_sell_computes_per_m2(self):
        total, monthly, per_m2 = _parse_price_fields("125 000 €", "sell", 68.5)
        assert total == 125000.0
        assert per_m2 == pytest.approx(125000.0 / 68.5, rel=1e-3)

    def test_rent_monthly(self):
        total, monthly, per_m2 = _parse_price_fields("850 €/мес", "rent", None)
        assert monthly == 850.0
        assert total is None

    def test_rent_deal_type_forces_monthly(self):
        total, monthly, per_m2 = _parse_price_fields("850 €", "rent", None)
        assert monthly == 850.0
        assert total is None

    def test_per_m2_price(self):
        total, monthly, per_m2 = _parse_price_fields("1800 €/м²", "sell", 68.0)
        assert per_m2 == 1800.0
        assert total is None

    def test_none_price(self):
        assert _parse_price_fields(None, "sell", None) == (None, None, None)

    def test_unparseable_price(self):
        assert _parse_price_fields("Cena pēc vienošanās", "sell", None) == (None, None, None)


# ---------------------------------------------------------------------------
# _parse_location
# ---------------------------------------------------------------------------

class TestParseLocation:
    def test_full_three_part_address(self):
        district, street = _parse_location("Rīga, Centrs, Barona iela 15", "Barona iela 15")
        assert district == "Centrs"
        assert street == "Barona iela 15"

    def test_two_part_address(self):
        district, street = _parse_location("Rīga, Centrs", "Barona iela 15")
        assert district == "Centrs"
        assert street == "Barona iela 15"

    def test_none_city_text(self):
        district, street = _parse_location(None, "Barona iela 15")
        assert district is None
        assert street is None

    def test_single_part(self):
        district, street = _parse_location("Rīga", "Barona iela 15")
        assert district is None

    def test_multi_segment_street(self):
        district, street = _parse_location("Rīga, Pļavnieki, Lubānas iela, 22", "Lubānas iela")
        assert district == "Pļavnieki"
        assert "Lubānas iela" in street


# ---------------------------------------------------------------------------
# Full _parse_listings with HTML fixtures
# ---------------------------------------------------------------------------

_SELL_HTML = """
<html><body>
<table>
<tr id="tr_12345">
  <td><img src="/img/cl/small/a/b/12345.jpg" /></td>
  <td class="msga2"><a class="am" href="/msg/lv/real-estate/flats/riga/sell/12345/">Barona iela 15</a>Rīga, Centrs</td>
  <td class="msga2">3</td>
  <td class="msga2">68.5</td>
  <td class="msga2">3/9</td>
  <td class="msga2-o pp6"><a>125 000 €</a></td>
</tr>
</table>
</body></html>
"""

_RENT_HTML = """
<html><body>
<table>
<tr id="tr_67890">
  <td><img src="/img/cl/small/x/y/67890.jpg" /></td>
  <td class="msga2"><a class="am" href="/msg/lv/real-estate/flats/riga/hand_over/67890/">Lubānas iela 22</a>Rīga, Pļavnieki</td>
  <td class="msga2">2</td>
  <td class="msga2">52</td>
  <td class="msga2">4/9</td>
  <td class="msga2-o pp6"><a>650 €/мес</a></td>
</tr>
</table>
</body></html>
"""

_MINIMAL_HTML = """
<html><body>
<table>
<tr id="tr_11111">
  <td><a href="/msg/lv/transport/cars/11111/"><b>Toyota Corolla</b></a></td>
  <td class="msga2-o pp6"><a>12 500 €</a></td>
</tr>
</table>
</body></html>
"""


class TestParseListings:
    def _parse(self, html: str, base_url: str = "https://ss.lv/"):
        parser = SSParser()
        return parser._parse_listings(html=html, base_url=base_url, limit=20)

    def test_sell_listing_deal_type(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert len(listings) == 1
        assert listings[0].deal_type == "sell"

    def test_sell_listing_rooms(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].rooms == 3

    def test_sell_listing_area(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].area_m2 == 68.5

    def test_sell_listing_floor(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].floor_current == 3
        assert listings[0].floor_total == 9

    def test_sell_listing_price(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].price_total_eur == 125000.0

    def test_sell_listing_hd_image(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].image_url_hd is not None
        assert "/large/" in listings[0].image_url_hd

    def test_sell_listing_preview_image(self):
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert listings[0].image_url_preview is not None
        assert "/small/" in listings[0].image_url_preview

    def test_rent_listing_deal_type(self):
        listings = self._parse(
            _RENT_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/hand_over/",
        )
        assert listings[0].deal_type == "rent"

    def test_rent_listing_monthly_price(self):
        listings = self._parse(
            _RENT_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/hand_over/",
        )
        assert listings[0].price_monthly_eur == 650.0
        assert listings[0].price_total_eur is None

    def test_minimal_listing_no_crash(self):
        """Parser must not crash when optional fields are missing."""
        listings = self._parse(_MINIMAL_HTML)
        assert len(listings) == 1
        listing = listings[0]
        assert listing.rooms is None
        assert listing.area_m2 is None
        assert listing.floor_current is None
        assert listing.image_url_hd is None

    def test_backward_compat_fields_present(self):
        """Existing fields (title, url, price, city, photo_urls) still populated."""
        listings = self._parse(
            _SELL_HTML,
            base_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        l = listings[0]
        assert l.external_id == "12345"
        assert l.title == "Barona iela 15"
        assert "12345" in l.url
        assert l.price is not None
        assert len(l.photo_urls) == 1

    def test_limit_respected(self):
        # Duplicate the row to simulate 5 results, limit to 2
        row = """<tr id="tr_9999{i}">
          <td><a href="/msg/lv/foo/9999{i}/">Title {i}</a></td>
          <td class="msga2-o pp6"><a>100 €</a></td>
        </tr>"""
        rows = "".join(row.format(i=i) for i in range(5))
        html = f"<html><body><table>{rows}</table></body></html>"
        listings = SSParser()._parse_listings(html=html, base_url="https://ss.lv/", limit=2)
        assert len(listings) == 2


# ---------------------------------------------------------------------------
# Fixture for detail-page parsing
# ---------------------------------------------------------------------------

_DETAIL_HTML = """
<html><body>
<div class="msg_container">
  <table class="ads_parameters">
    <tr>
      <td class="ads_opt_name">Pilsēta</td>
      <td class="ads_opt">Rīga</td>
      <td class="ads_opt_name">Rajons</td>
      <td class="ads_opt">centrs</td>
    </tr>
    <tr>
      <td class="ads_opt_name">Iela</td>
      <td class="ads_opt">Veru 3</td>
      <td class="ads_opt_name">Istabas</td>
      <td class="ads_opt">3</td>
    </tr>
    <tr>
      <td class="ads_opt_name">Platība</td>
      <td class="ads_opt">63 m²</td>
      <td class="ads_opt_name">Stāvs</td>
      <td class="ads_opt">1/5</td>
    </tr>
    <tr>
      <td class="ads_opt_name">Sērija</td>
      <td class="ads_opt">P. kara</td>
      <td class="ads_opt_name">Mājas tips</td>
      <td class="ads_opt">Mūra</td>
    </tr>
    <tr>
      <td class="ads_opt_name">Cena</td>
      <td class="ads_opt">125 000 €</td>
    </tr>
  </table>
  <img src="https://i.ss.lv/img/cl/large/a/b/12345.jpg" />
</div>
</body></html>
"""

_DETAIL_HTML_NBSP_PRICE = """
<html><body>
<table class="ads_parameters">
  <tr>
    <td class="ads_opt_name">Cena</td>
    <td class="ads_opt">125\u00a0000\u00a0€</td>
  </tr>
</table>
</body></html>
"""

_DETAIL_HTML_RENT = """
<html><body>
<table class="ads_parameters">
  <tr>
    <td class="ads_opt_name">Cena</td>
    <td class="ads_opt">3 500 €/mēn</td>
  </tr>
</table>
</body></html>
"""

_DETAIL_HTML_IMAGE_VARIANTS = """
<html><body>
<a href="https://i.ss.lv/img/cl/large/a/b/111.jpg">large</a>
<a href="https://i.ss.lv/img/cl/original/a/b/111.jpg">original</a>
<img src="https://i.ss.lv/img/cl/small/a/b/111.jpg" />
</body></html>
"""


# ---------------------------------------------------------------------------
# parse_detail_page
# ---------------------------------------------------------------------------

class TestParseDetailPage:
    def test_city(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["city"] == "Rīga"

    def test_district(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["district"] == "centrs"

    def test_street(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["street"] == "Veru 3"

    def test_rooms(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["rooms"] == 3

    def test_area_m2(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["area_m2"] == 63.0

    def test_floor_current(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["floor_current"] == 1

    def test_floor_total(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["floor_total"] == 5

    def test_series(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["series"] == "P. kara"

    def test_house_type(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["house_type"] == "Mūra"

    def test_price_raw(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data["price_raw"] == "125 000 €"

    def test_image_url_hd(self):
        data = parse_detail_page(_DETAIL_HTML)
        assert data.get("image_url_hd") == "https://i.ss.lv/img/cl/large/a/b/12345.jpg"

    def test_image_selection_prefers_original_then_large_then_preview(self):
        data = parse_detail_page(_DETAIL_HTML_IMAGE_VARIANTS)
        assert data.get("image_url_hd") == "https://i.ss.lv/img/cl/original/a/b/111.jpg"

    def test_missing_spec_table_no_crash(self):
        data = parse_detail_page("<html><body><p>No spec table</p></body></html>")
        assert isinstance(data, dict)
        assert "city" not in data

    def test_empty_html_no_crash(self):
        data = parse_detail_page("")
        assert isinstance(data, dict)

    def test_case_insensitive_label_matching(self):
        html = """<html><body>
        <table class="ads_parameters">
          <tr>
            <td class="ads_opt_name">MĀJAS TIPS</td>
            <td class="ads_opt">Mūra</td>
          </tr>
        </table></body></html>"""
        data = parse_detail_page(html)
        assert data.get("house_type") == "Mūra"

    def test_nbsp_price_parsed(self):
        data = parse_detail_page(_DETAIL_HTML_NBSP_PRICE)
        assert data.get("price_raw") is not None
        # Must contain digits, not truncated
        assert "125" in data["price_raw"]


# ---------------------------------------------------------------------------
# enrich_listing_from_detail
# ---------------------------------------------------------------------------

def _base_listing(**kwargs) -> Listing:
    defaults = dict(
        external_id="99999",
        title="Test",
        url="https://ss.lv/msg/lv/real-estate/flats/riga/sell/99999/",
        deal_type="sell",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


class TestEnrichListingFromDetail:
    def test_fields_populated(self):
        listing = _base_listing()
        detail = {
            "city": "Rīga",
            "district": "centrs",
            "street": "Veru 3",
            "rooms": 3,
            "area_m2": 63.0,
            "floor_current": 1,
            "floor_total": 5,
            "series": "P. kara",
            "house_type": "Mūra",
            "price_raw": "125 000 €",
        }
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched.city == "Rīga"
        assert enriched.district == "centrs"
        assert enriched.street == "Veru 3"
        assert enriched.rooms == 3
        assert enriched.area_m2 == 63.0
        assert enriched.floor_current == 1
        assert enriched.floor_total == 5
        assert enriched.series == "P. kara"
        assert enriched.house_type == "Mūra"

    def test_sell_price_total(self):
        listing = _base_listing(deal_type="sell")
        detail = {"price_raw": "125 000 €"}
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched.price_total_eur == 125000.0
        assert enriched.price_monthly_eur is None

    def test_sell_price_per_m2_computed(self):
        listing = _base_listing(deal_type="sell")
        detail = {"price_raw": "125 000 €", "area_m2": 63.0}
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched.price_per_m2_eur == pytest.approx(125000 / 63, rel=1e-3)

    def test_rent_price_monthly(self):
        listing = _base_listing(deal_type="rent")
        detail = {"price_raw": "3 500 €/mēn"}
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched.price_monthly_eur == 3500.0
        assert enriched.price_total_eur is None

    def test_original_unchanged(self):
        listing = _base_listing()
        detail = {"city": "Rīga"}
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched is not listing
        assert listing.city is None

    def test_empty_detail_returns_same_object(self):
        listing = _base_listing()
        result = enrich_listing_from_detail(listing, {})
        assert result is listing

    def test_image_url_hd_enriched(self):
        listing = _base_listing()
        detail = {"image_url_hd": "https://i.ss.lv/img/cl/large/a/b/1.jpg"}
        enriched = enrich_listing_from_detail(listing, detail)
        assert enriched.image_url_hd == "https://i.ss.lv/img/cl/large/a/b/1.jpg"


# ---------------------------------------------------------------------------
# Price parsing regression — no truncation
# ---------------------------------------------------------------------------

class TestPriceParsingRegression:
    def test_125000_spaces(self):
        assert normalize_price_eur("125 000 €") == 125000.0

    def test_125000_nbsp(self):
        assert normalize_price_eur("125\u00a0000\u00a0€") == 125000.0

    def test_3500_monthly(self):
        assert normalize_price_eur("3 500 €/mēn") == 3500.0

    def test_1984_per_m2(self):
        assert normalize_price_eur("1 984 €/m²") == 1984.0

    def test_no_truncation_to_single_digit(self):
        """Regression: '125 000 €' must never produce a value < 100."""
        result = normalize_price_eur("125 000 €")
        assert result is not None
        assert result >= 100

    def test_3_eur_is_not_result_of_125000(self):
        """'125 000 €' must not parse to 3."""
        assert normalize_price_eur("125 000 €") != 3.0
