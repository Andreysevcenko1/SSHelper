"""Tests for app.services.formatter — deal_type, image selection, price
normalisation, template selection, and message rendering."""

import pytest

from app.services.formatter import (
    detect_deal_type,
    format_generic_message,
    format_listing_message,
    format_price,
    format_rent_message,
    format_sell_message,
    normalize_price_eur,
    select_image_url,
    upgrade_image_url,
)
from app.services.ss_parser import Listing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _listing(**kwargs) -> Listing:
    defaults = dict(
        external_id="12345",
        title="Barona iela 15",
        url="https://ss.lv/msg/lv/real-estate/flats/riga/12345/",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


# ---------------------------------------------------------------------------
# detect_deal_type
# ---------------------------------------------------------------------------

class TestDetectDealType:
    def test_hand_over_is_rent(self):
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/hand_over/") == "rent"

    def test_sell_is_sell(self):
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/sell/") == "sell"

    def test_ire_segment_is_rent(self):
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/ire/") == "rent"

    def test_pardosana_is_sell(self):
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/pardosana/") == "sell"

    def test_unknown_url(self):
        assert detect_deal_type("https://ss.lv/lv/transport/cars/riga/") == "unknown"

    def test_case_insensitive(self):
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/HAND_OVER/") == "rent"
        assert detect_deal_type("https://ss.lv/lv/real-estate/flats/riga/SELL/") == "sell"


# ---------------------------------------------------------------------------
# upgrade_image_url
# ---------------------------------------------------------------------------

class TestUpgradeImageUrl:
    def test_small_to_large(self):
        url = "https://i.ss.lv/img/cl/small/abc/def/12345.jpg"
        assert upgrade_image_url(url) == "https://i.ss.lv/img/cl/large/abc/def/12345.jpg"

    def test_no_small_segment_unchanged(self):
        url = "https://i.ss.lv/img/cl/orig/abc/def/12345.jpg"
        assert upgrade_image_url(url) == url

    def test_case_insensitive_small(self):
        url = "https://i.ss.lv/img/cl/Small/abc/12345.jpg"
        assert "small" not in upgrade_image_url(url).lower() or "large" in upgrade_image_url(url).lower()


# ---------------------------------------------------------------------------
# normalize_price_eur
# ---------------------------------------------------------------------------

class TestNormalizePriceEur:
    def test_basic_integer(self):
        assert normalize_price_eur("125000") == 125000.0

    def test_with_euro_symbol(self):
        assert normalize_price_eur("125 000 €") == 125000.0

    def test_nbsp_separator(self):
        assert normalize_price_eur("125\u00a0000\u00a0€") == 125000.0

    def test_thin_space_separator(self):
        assert normalize_price_eur("125\u202f000 €") == 125000.0

    def test_monthly_price(self):
        assert normalize_price_eur("850 €/мес") == 850.0

    def test_none_input(self):
        assert normalize_price_eur(None) is None

    def test_empty_string(self):
        assert normalize_price_eur("") is None

    def test_non_numeric(self):
        assert normalize_price_eur("Cena pēc vienošanās") is None

    def test_decimal_dot(self):
        assert normalize_price_eur("1234.50 €") == 1234.5

    def test_decimal_comma(self):
        assert normalize_price_eur("1234,50 €") == 1234.5

    def test_large_price(self):
        assert normalize_price_eur("1 250 000 €") == 1250000.0

    def test_eur_suffix(self):
        assert normalize_price_eur("85000 EUR") == 85000.0


# ---------------------------------------------------------------------------
# format_price
# ---------------------------------------------------------------------------

class TestFormatPrice:
    def test_integer_value(self):
        assert format_price(125000.0) == "125\u202f000 €"

    def test_zero(self):
        assert format_price(0.0) == "0 €"

    def test_none(self):
        assert format_price(None) is None

    def test_custom_unit(self):
        result = format_price(850.0, "€/мес")
        assert result == "850 €/мес"

    def test_per_m2_unit(self):
        result = format_price(1838.0, "€/м²")
        assert "1\u202f838" in result


# ---------------------------------------------------------------------------
# select_image_url
# ---------------------------------------------------------------------------

class TestSelectImageUrl:
    def test_hd_preferred(self):
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
            photo_urls=["https://i.ss.lv/img/cl/small/abc/1.jpg"],
        )
        assert select_image_url(listing) == "https://i.ss.lv/img/cl/large/abc/1.jpg"

    def test_photo_urls_upgraded_when_no_hd(self):
        listing = _listing(
            image_url_hd=None,
            photo_urls=["https://i.ss.lv/img/cl/small/abc/1.jpg"],
        )
        result = select_image_url(listing)
        assert result == "https://i.ss.lv/img/cl/large/abc/1.jpg"

    def test_preview_not_used_as_fallback(self):
        """select_image_url must return None when only image_url_preview is available.

        We must never send a raw thumbnail — callers should fall back to text.
        """
        listing = _listing(
            image_url_hd=None,
            photo_urls=[],
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
        )
        assert select_image_url(listing) is None

    def test_none_when_no_images(self):
        listing = _listing(image_url_hd=None, photo_urls=[], image_url_preview=None)
        assert select_image_url(listing) is None

    def test_photo_url_no_upgrade_if_no_small_segment(self):
        url = "https://i.ss.lv/img/cl/orig/abc/1.jpg"
        listing = _listing(image_url_hd=None, photo_urls=[url])
        assert select_image_url(listing) == url


# ---------------------------------------------------------------------------
# format_sell_message
# ---------------------------------------------------------------------------

class TestFormatSellMessage:
    def test_full_fields(self):
        listing = _listing(
            title="Barona iela 15",
            district="Centrs",
            street="Barona iela 15",
            rooms=3,
            area_m2=68.5,
            floor_current=3,
            floor_total=9,
            house_type="Sērijas",
            price_per_m2_eur=1838.0,
            price_total_eur=125830.0,
            deal_type="sell",
        )
        msg = format_sell_message(listing)
        assert "🏙 Район: Centrs" in msg
        assert "📍 Улица: Barona iela 15" in msg
        assert "🛏 Комнат: 3" in msg
        assert "📐 Площадь: 68.5" in msg
        assert "🏢 Этаж: 3/9" in msg
        assert "🧱 Тип дома: Sērijas" in msg
        assert "💶 Цена за м²" in msg
        assert "💰 Полная цена" in msg
        assert listing.url in msg

    def test_missing_fields_omitted(self):
        listing = _listing(
            deal_type="sell",
            district=None,
            street=None,
            rooms=None,
            area_m2=None,
            floor_current=None,
            floor_total=None,
            house_type=None,
            price_per_m2_eur=None,
            price_total_eur=125000.0,
        )
        msg = format_sell_message(listing)
        assert "🏙 Район" not in msg
        assert "📍 Улица" not in msg
        assert "🛏 Комнат" not in msg
        assert "📐 Площадь" not in msg
        assert "🏢 Этаж" not in msg
        assert "💶 Цена за м²" not in msg
        assert "💰 Полная цена" in msg

    def test_floor_without_total(self):
        listing = _listing(deal_type="sell", floor_current=5, floor_total=None)
        msg = format_sell_message(listing)
        assert "🏢 Этаж: 5" in msg
        assert "/" not in msg.split("Этаж:")[1].split("\n")[0]

    def test_url_always_present(self):
        listing = _listing(deal_type="sell")
        msg = format_sell_message(listing)
        assert listing.url in msg

    def test_html_escape_in_title(self):
        listing = _listing(title="A <& B", deal_type="sell")
        msg = format_sell_message(listing)
        assert "<& " not in msg  # raw < should be escaped
        assert "&amp;" in msg or "&lt;" in msg


# ---------------------------------------------------------------------------
# format_rent_message
# ---------------------------------------------------------------------------

class TestFormatRentMessage:
    def test_full_fields(self):
        listing = _listing(
            district="Pļavnieki",
            street="Lubānas iela 22",
            rooms=2,
            area_m2=52.0,
            floor_current=4,
            floor_total=9,
            price_monthly_eur=650.0,
            deal_type="rent",
        )
        msg = format_rent_message(listing)
        assert "🏙 Район: Pļavnieki" in msg
        assert "📍 Улица: Lubānas iela 22" in msg
        assert "🛏 Комнат: 2" in msg
        assert "📐 Площадь: 52.0" in msg
        assert "🏢 Этаж: 4/9" in msg
        assert "💶 Цена в месяц" in msg
        # Must NOT include sell-specific fields
        assert "💰 Полная цена" not in msg
        assert "💶 Цена за м²" not in msg

    def test_missing_price_omitted(self):
        listing = _listing(deal_type="rent", price_monthly_eur=None)
        msg = format_rent_message(listing)
        assert "💶 Цена в месяц" not in msg

    def test_url_always_present(self):
        listing = _listing(deal_type="rent")
        msg = format_rent_message(listing)
        assert listing.url in msg


# ---------------------------------------------------------------------------
# format_generic_message
# ---------------------------------------------------------------------------

class TestFormatGenericMessage:
    def test_with_price_and_city(self):
        listing = _listing(price="125 000 €", city="Rīga")
        msg = format_generic_message(listing)
        assert "💰 125 000 €" in msg
        assert "📍 Rīga" in msg
        assert listing.url in msg

    def test_without_optional_fields(self):
        listing = _listing()
        msg = format_generic_message(listing)
        assert listing.url in msg

    def test_title_bold(self):
        listing = _listing(title="Test Listing")
        msg = format_generic_message(listing)
        assert "<b>Test Listing</b>" in msg


# ---------------------------------------------------------------------------
# format_listing_message — dispatch
# ---------------------------------------------------------------------------

class TestFormatListingMessage:
    def test_dispatches_to_sell(self):
        listing = _listing(
            deal_type="sell",
            price_total_eur=100000.0,
            url="https://ss.lv/msg/lv/real-estate/flats/riga/sell/12345/",
        )
        msg = format_listing_message(listing)
        assert "💰 Полная цена" in msg

    def test_dispatches_to_rent(self):
        listing = _listing(
            deal_type="rent",
            price_monthly_eur=800.0,
            url="https://ss.lv/msg/lv/real-estate/flats/riga/hand_over/12345/",
        )
        msg = format_listing_message(listing)
        assert "💶 Цена в месяц" in msg

    def test_fallback_to_generic_when_unknown(self):
        listing = _listing(deal_type="unknown", price="123 €", city="Rīga")
        msg = format_listing_message(listing)
        assert "💰 123 €" in msg

    def test_infers_rent_from_search_url(self):
        listing = _listing(deal_type="unknown", price_monthly_eur=700.0)
        msg = format_listing_message(
            listing,
            search_url="https://ss.lv/lv/real-estate/flats/riga/hand_over/",
        )
        assert "💶 Цена в месяц" in msg

    def test_infers_sell_from_search_url(self):
        listing = _listing(deal_type="unknown", price_total_eur=150000.0)
        msg = format_listing_message(
            listing,
            search_url="https://ss.lv/lv/real-estate/flats/riga/sell/",
        )
        assert "💰 Полная цена" in msg

    def test_listing_deal_type_takes_priority_over_search_url(self):
        # listing.deal_type='sell' wins over a rent search_url
        listing = _listing(deal_type="sell", price_total_eur=200000.0)
        msg = format_listing_message(
            listing,
            search_url="https://ss.lv/lv/real-estate/flats/riga/hand_over/",
        )
        assert "💰 Полная цена" in msg
        assert "💶 Цена в месяц" not in msg


# ---------------------------------------------------------------------------
# Additional tests required by P0 hotfix
# ---------------------------------------------------------------------------

class TestUpgradeImageUrlThumb:
    """upgrade_image_url should also handle /thumb/ segments."""

    def test_thumb_to_large(self):
        url = "https://i.ss.lv/img/cl/thumb/abc/def/12345.jpg"
        assert upgrade_image_url(url) == "https://i.ss.lv/img/cl/large/abc/def/12345.jpg"

    def test_small_still_upgraded(self):
        url = "https://i.ss.lv/img/cl/small/abc/def/12345.jpg"
        assert upgrade_image_url(url) == "https://i.ss.lv/img/cl/large/abc/def/12345.jpg"


class TestSelectImageUrlNoPreviousFallback:
    """select_image_url must never return a raw preview/thumbnail URL."""

    def test_none_when_only_preview_available(self):
        """No photo_urls and only image_url_preview → must return None."""
        listing = _listing(
            image_url_hd=None,
            photo_urls=[],
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
        )
        assert select_image_url(listing) is None

    def test_hd_image_priority_over_preview(self):
        """image_url_hd is returned even when preview is also present."""
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
            photo_urls=[],
        )
        assert select_image_url(listing) == "https://i.ss.lv/img/cl/large/abc/1.jpg"

    def test_thumb_photo_url_upgraded(self):
        """photo_urls entry with /thumb/ is upgraded to /large/."""
        listing = _listing(
            image_url_hd=None,
            photo_urls=["https://i.ss.lv/img/cl/thumb/abc/1.jpg"],
            image_url_preview="https://i.ss.lv/img/cl/thumb/abc/1.jpg",
        )
        assert select_image_url(listing) == "https://i.ss.lv/img/cl/large/abc/1.jpg"


class TestSellTemplatePartialFields:
    """Sell template renders correctly when only some fields are populated."""

    def test_only_price_total_present(self):
        listing = _listing(
            deal_type="sell",
            price_total_eur=99000.0,
            district=None, street=None, rooms=None,
            area_m2=None, floor_current=None, floor_total=None,
            house_type=None, price_per_m2_eur=None,
        )
        msg = format_sell_message(listing)
        # Populated field present
        assert "💰 Полная цена" in msg
        # URL always present
        assert listing.url in msg
        # Empty fields omitted
        assert "🏙 Район" not in msg
        assert "🛏 Комнат" not in msg

    def test_three_fields_present(self):
        listing = _listing(
            deal_type="sell",
            district="Centrs",
            rooms=2,
            price_total_eur=85000.0,
            street=None, area_m2=None,
            floor_current=None, floor_total=None,
            house_type=None, price_per_m2_eur=None,
        )
        msg = format_sell_message(listing)
        assert "🏙 Район: Centrs" in msg
        assert "🛏 Комнат: 2" in msg
        assert "💰 Полная цена" in msg
        assert "📍 Улица" not in msg
        assert listing.url in msg


class TestRentTemplatePartialFields:
    """Rent template renders correctly when only some fields are populated."""

    def test_only_monthly_price_present(self):
        listing = _listing(
            deal_type="rent",
            price_monthly_eur=500.0,
            district=None, street=None, rooms=None,
            area_m2=None, floor_current=None, floor_total=None,
            house_type=None,
        )
        msg = format_rent_message(listing)
        assert "💶 Цена в месяц" in msg
        assert listing.url in msg
        assert "🏙 Район" not in msg

    def test_district_and_rooms_no_price(self):
        listing = _listing(
            deal_type="rent",
            district="Purvciems",
            rooms=3,
            price_monthly_eur=None,
        )
        msg = format_rent_message(listing)
        assert "🏙 Район: Purvciems" in msg
        assert "🛏 Комнат: 3" in msg
        assert "💶 Цена в месяц" not in msg
        assert listing.url in msg


class TestNoPhotoOnlyCaption:
    """format_listing_message always returns a non-empty text with a URL line."""

    def test_sell_always_has_url(self):
        listing = _listing(deal_type="sell")
        msg = format_listing_message(listing)
        assert listing.url in msg

    def test_rent_always_has_url(self):
        listing = _listing(deal_type="rent")
        msg = format_listing_message(listing)
        assert listing.url in msg

    def test_generic_always_has_url(self):
        listing = _listing(deal_type="unknown")
        msg = format_listing_message(listing)
        assert listing.url in msg

    def test_sell_full_fields_has_five_or_more_structured_lines(self):
        """Acceptance criterion: ≥5 structured lines + link for a well-populated listing."""
        listing = _listing(
            deal_type="sell",
            district="Centrs",
            street="Barona 15",
            rooms=3,
            area_m2=68.0,
            floor_current=3,
            floor_total=9,
            house_type="Sērijas",
            price_total_eur=125000.0,
            price_per_m2_eur=1838.0,
        )
        msg = format_listing_message(listing)
        structured_lines = [
            l for l in msg.splitlines()
            if any(emoji in l for emoji in ("🏙", "📍", "🛏", "📐", "🏢", "🧱", "💶", "💰"))
        ]
        assert len(structured_lines) >= 5, f"Expected ≥5 structured lines, got {len(structured_lines)}"
        assert listing.url in msg

    def test_no_raw_opt_keys_in_output(self):
        """No raw opt[ or topt[ keys should appear in any rendered message."""
        listing = _listing(deal_type="sell", district="X", price_total_eur=1.0)
        msg = format_listing_message(listing)
        assert "opt[" not in msg
        assert "topt[" not in msg
