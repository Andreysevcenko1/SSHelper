"""
Unified notification message formatter for SS.lv listings.

Provides:
- deal_type detection from URL
- HD image URL upgrading and selection
- sell / rent / generic message templates
- price normalisation helpers
"""

from __future__ import annotations

import logging
import re
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ss_parser import Listing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deal-type detection
# ---------------------------------------------------------------------------

_RENT_URL_RE = re.compile(r'/hand[_-]?over/|/ire/|/rent/|/iznoma/', re.IGNORECASE)
_SELL_URL_RE = re.compile(r'/sell/|/pardosana/|/pirkt/|/sale/', re.IGNORECASE)


def detect_deal_type(url: str) -> str:
    """Return ``'sell'``, ``'rent'``, or ``'unknown'`` from a listing / search URL."""
    if _RENT_URL_RE.search(url):
        return "rent"
    if _SELL_URL_RE.search(url):
        return "sell"
    return "unknown"


# ---------------------------------------------------------------------------
# Image URL upgrading
# ---------------------------------------------------------------------------

def upgrade_image_url(url: str) -> str:
    """
    Try to convert a thumbnail URL to the highest-resolution variant.

    SS.lv uses ``/small/`` and ``/thumb/`` path segments for previews;
    replacing either with ``/large/`` gives the full-size image.
    """
    upgraded = re.sub(r'/(small|thumb)/', '/large/', url, flags=re.IGNORECASE)
    return upgraded


# ---------------------------------------------------------------------------
# Image selection
# ---------------------------------------------------------------------------

def select_image_url(listing: "Listing") -> str | None:
    """
    Return the best available HD image URL in priority order:

    1. ``listing.image_url_hd``  (explicit HD URL stored by the parser)
    2. First entry of ``listing.photo_urls`` — returned as-is when already
       HD-looking, or after a size-segment upgrade (``/small/``→``/large/``).
    3. ``None`` — never returns a raw preview/thumbnail URL.

    Callers that receive ``None`` must fall back to a text-only message rather
    than sending a blurry low-resolution thumbnail.
    """
    if listing.image_url_hd:
        logger.debug(
            "Image selected: explicit hd for listing %s → %s",
            listing.external_id, listing.image_url_hd,
        )
        return listing.image_url_hd

    if listing.photo_urls:
        original = listing.photo_urls[0]
        upgraded = upgrade_image_url(original)
        if upgraded != original:
            logger.debug(
                "Image selected: upgraded to large for listing %s → %s",
                listing.external_id, upgraded,
            )
        else:
            logger.debug(
                "Image selected: photo_url (no size upgrade) for listing %s → %s",
                listing.external_id, original,
            )
        return upgraded

    logger.debug("Image selected: none available for listing %s (preview omitted)", listing.external_id)
    return None


# ---------------------------------------------------------------------------
# Price normalisation
# ---------------------------------------------------------------------------

def normalize_price_eur(price_str: str | None) -> float | None:
    """
    Parse a price string like ``'125 000 €'`` or ``'850 €/мес'`` to ``float``.

    Returns ``None`` when *price_str* is ``None``, empty, or unparseable.
    """
    if not price_str:
        return None

    # Strip currency symbols and unit suffixes
    cleaned = re.sub(r'[€$£]', '', price_str)
    cleaned = re.sub(r'(?i)(eur|usd|/m[eē]n[eē]?|/month|/мес[яц]*|м²|m²|/m²|/м²)', '', cleaned)
    # Remove all whitespace variants (regular, NBSP, thin space, narrow NBSP, …)
    cleaned = re.sub(r'[\s\u00a0\u202f\u2009\u00b7]', '', cleaned)
    # Keep only digits and decimal separators
    cleaned = re.sub(r'[^\d.,]', '', cleaned)

    if not cleaned:
        return None

    dot_count = cleaned.count('.')
    comma_count = cleaned.count(',')

    try:
        if dot_count == 0 and comma_count == 0:
            # Plain integer (thousands stripped above)
            return float(cleaned)

        if dot_count == 1 and comma_count == 0:
            # "1234.56" — decimal dot
            return float(cleaned)

        if comma_count == 1 and dot_count == 0:
            # "1234,56" — decimal comma
            return float(cleaned.replace(',', '.'))

        # Multiple separators → treat all as thousands separators (strip them)
        cleaned = cleaned.replace(',', '').replace('.', '')
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Price display formatting
# ---------------------------------------------------------------------------

def format_price(value: float | None, unit: str = "€") -> str | None:
    """
    Format a numeric price for Telegram display.

    Uses a thin space (U+202F) as a thousands separator so the number looks
    like ``125\u202f000 €``.  Returns ``None`` when *value* is ``None``.
    """
    if value is None:
        return None
    # Use integer representation when there is no fractional part
    int_val = int(value)
    display = int_val if value == int_val else round(value, 2)
    formatted = f"{display:,}".replace(",", "\u202f")
    return f"{formatted} {unit}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _opt_line(emoji_label: str, value: object) -> str | None:
    """Return ``'emoji_label: <escaped value>'`` or ``None`` when value is absent."""
    if value is None or str(value).strip() == "":
        return None
    return f"{emoji_label}: {escape(str(value))}"


def _floor_str(floor_current: int | None, floor_total: int | None) -> str | None:
    if floor_current is not None and floor_total is not None:
        return f"{floor_current}/{floor_total}"
    if floor_current is not None:
        return str(floor_current)
    return None


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

def format_sell_message(listing: "Listing") -> str:
    """Render the **SELL** notification card (HTML parse mode)."""
    logger.debug("Message template selected: sell for listing %s", listing.external_id)

    area_str = f"{listing.area_m2}\u202fм²" if listing.area_m2 is not None else None
    floor_str = _floor_str(listing.floor_current, listing.floor_total)
    per_m2_str = format_price(listing.price_per_m2_eur, "€/м²")
    total_str = format_price(listing.price_total_eur, "€")

    lines: list[str] = [f"<b>{escape(listing.title)}</b>"]
    for line in [
        _opt_line("🏙 Район", listing.district),
        _opt_line("📍 Улица", listing.street),
        _opt_line("🛏 Комнат", listing.rooms),
        _opt_line("📐 Площадь", area_str),
        _opt_line("🏢 Этаж", floor_str),
        _opt_line("🏗 Серия", listing.series),
        _opt_line("🧱 Тип дома", listing.house_type),
        _opt_line("💶 Цена за м²", per_m2_str),
        _opt_line("💰 Полная цена", total_str),
    ]:
        if line:
            lines.append(line)

    lines.append(f"🔗 {listing.url}")
    return "\n".join(lines)


def format_rent_message(listing: "Listing") -> str:
    """Render the **RENT** notification card (HTML parse mode)."""
    logger.debug("Message template selected: rent for listing %s", listing.external_id)

    area_str = f"{listing.area_m2}\u202fм²" if listing.area_m2 is not None else None
    floor_str = _floor_str(listing.floor_current, listing.floor_total)
    monthly_str = format_price(listing.price_monthly_eur, "€/мес")

    lines: list[str] = [f"<b>{escape(listing.title)}</b>"]
    for line in [
        _opt_line("🏙 Район", listing.district),
        _opt_line("📍 Улица", listing.street),
        _opt_line("🛏 Комнат", listing.rooms),
        _opt_line("📐 Площадь", area_str),
        _opt_line("🏢 Этаж", floor_str),
        _opt_line("🏗 Серия", listing.series),
        _opt_line("🧱 Тип дома", listing.house_type),
        _opt_line("💶 Цена в месяц", monthly_str),
    ]:
        if line:
            lines.append(line)

    lines.append(f"🔗 {listing.url}")
    return "\n".join(lines)


def format_generic_message(listing: "Listing") -> str:
    """Render a generic notification when deal_type is unknown (HTML parse mode)."""
    logger.debug("Message template selected: generic for listing %s", listing.external_id)

    lines: list[str] = [f"<b>{escape(listing.title)}</b>"]
    if listing.price:
        lines.append(f"💰 {escape(listing.price)}")
    if listing.city:
        lines.append(f"📍 {escape(listing.city)}")
    lines.append(f"🔗 {listing.url}")
    return "\n".join(lines)


def format_listing_message(listing: "Listing", search_url: str | None = None) -> str:
    """
    Select and render the appropriate message template.

    Uses ``listing.deal_type`` first; if it is ``'unknown'`` and *search_url*
    is provided, attempts to infer the deal_type from the URL.  Falls back to
    the generic template when still unknown.
    """
    deal_type = listing.deal_type

    if deal_type == "unknown" and search_url:
        deal_type = detect_deal_type(search_url)

    if deal_type == "sell":
        return format_sell_message(listing)
    if deal_type == "rent":
        return format_rent_message(listing)
    return format_generic_message(listing)
