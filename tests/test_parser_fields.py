"""Tests for the real-estate field extraction helpers in ss_parser."""

import pytest
from bs4 import BeautifulSoup

from app.services.ss_parser import (
    SSParser,
    _parse_location,
    _parse_price_fields,
    _parse_realestate_cells,
    _try_parse_area,
    _try_parse_floor,
    _try_parse_rooms,
    normalize_price_eur,
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
