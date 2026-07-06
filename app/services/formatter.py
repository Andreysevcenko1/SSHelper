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


def _image_quality_rank(url: str) -> int:
    """Return quality rank for *url*: 3=full/original, 2=large, 1=preview, 0=unknown."""
    lowered = url.lower()
    if any(token in lowered for token in ("/original/", "/orig/", "/full/")):
        return 3
    if "/large/" in lowered:
        return 2
    if any(token in lowered for token in ("/small/", "/thumb/", "/preview/")):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Image selection
# ---------------------------------------------------------------------------

def select_image_url(listing: "Listing") -> str | None:
    """
    Return the best available HD image URL in priority order:

    1. ``listing.image_url_hd``  (explicit HD URL from detail/gallery)
    2. Largest variant from ``listing.photo_urls`` (with size upgrade when possible)
    3. ``listing.image_url_preview`` (last resort)
    4. ``None`` when no image URL is available.
    """
    if listing.image_url_hd:
        logger.debug(
            "Image selected: explicit hd for listing %s → %s",
            listing.external_id, listing.image_url_hd,
        )
        return listing.image_url_hd

    if listing.photo_urls:
        variants: list[str] = []
        for original in listing.photo_urls:
            upgraded = upgrade_image_url(original)
            variants.append(upgraded)
            if upgraded != original:
                variants.append(original)
        best = max(variants, key=_image_quality_rank)
        logger.debug(
            "Image selected: best gallery variant for listing %s → %s (rank=%s)",
            listing.external_id,
            best,
            _image_quality_rank(best),
        )
        return best

    if listing.image_url_preview:
        logger.debug(
            "Image selected: preview fallback for listing %s → %s",
            listing.external_id,
            listing.image_url_preview,
        )
        return listing.image_url_preview

    logger.debug("Image selected: none available for listing %s", listing.external_id)
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


_PRICE_TOKEN_RE = r"\d[\d\s\u00a0\u202f.,]*\s*(?:€|eur)"
_MONTHLY_RE = re.compile(rf"({_PRICE_TOKEN_RE}\s*/\s*m[ēe]n(?:e[sš]i)?\.?)", re.IGNORECASE)
_PER_M2_RE = re.compile(rf"({_PRICE_TOKEN_RE}\s*/\s*m²)", re.IGNORECASE)
_TOTAL_RE = re.compile(rf"({_PRICE_TOKEN_RE})(?!\s*/)", re.IGNORECASE)


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_price_token(token: str) -> str:
    normalized = _normalize_spaces(token.strip("() "))
    normalized = re.sub(r"(?i)eur", "€", normalized)
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"(?i)/m[eē]n(?:e[sš]i)?\.?", "/mēn.", normalized)
    normalized = re.sub(r"(?i)/m2", "/m²", normalized)
    return normalized


def _render_flats_price(raw_cena: str | None, deal_type: str | None) -> str | None:
    if not raw_cena:
        return None

    source = _normalize_spaces(raw_cena)
    monthly = _MONTHLY_RE.search(source)
    per_m2 = _PER_M2_RE.search(source)
    total = _TOTAL_RE.search(source)

    monthly_str = _normalize_price_token(monthly.group(1)) if monthly else None
    per_m2_str = _normalize_price_token(per_m2.group(1)) if per_m2 else None
    total_str = _normalize_price_token(total.group(1)) if total else None

    if deal_type == "rent":
        if monthly_str and per_m2_str:
            return f"{monthly_str} ({per_m2_str})"
        if monthly_str:
            return monthly_str
        return source

    if deal_type == "sell":
        if total_str and per_m2_str:
            return f"{total_str} ({per_m2_str})"
        if total_str:
            return total_str
        return source

    if monthly_str and per_m2_str:
        return f"{monthly_str} ({per_m2_str})"
    if total_str and per_m2_str:
        return f"{total_str} ({per_m2_str})"
    return monthly_str or total_str or source


def _format_area_lv(area_m2: float | None) -> str | None:
    if area_m2 is None:
        return None
    display = int(area_m2) if area_m2 == int(area_m2) else area_m2
    return f"{display} m²"


_TITLE_PRICE_RE = re.compile(r"\d[\d\s\u00a0\u202f.,]*\s*(?:€|EUR)\b", re.IGNORECASE)


def _extract_price_from_text(text: str | None) -> str | None:
    if not text:
        return None
    match = _TITLE_PRICE_RE.search(text)
    if not match:
        return None
    return _normalize_spaces(match.group(0))


def _cars_fallback_price(listing: "Listing") -> tuple[str, str]:
    if listing.price and str(listing.price).strip():
        return str(listing.price).strip(), "card"
    title_price = _extract_price_from_text(listing.title)
    if title_price:
        return title_price, "title"
    raw_price = listing.detail_raw_cena and str(listing.detail_raw_cena).strip()
    if raw_price:
        return str(raw_price), "raw_text"
    return "nav norādīta", "none"


def _cars_model_fallback(listing: "Listing") -> str:
    if getattr(listing, "car_make", None):
        return str(listing.car_make).strip()
    title = listing.title.strip()
    return title if title else "nav norādīts"


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


def format_flats_message(listing: "Listing", deal_type: str | None = None) -> str:
    """Render flats notifications using detail-page Latvian fields and strict price rules."""
    resolved_deal_type = deal_type if deal_type is not None else listing.deal_type

    if listing.detail_fetch_ok is None:
        area_str = f"{listing.area_m2}\u202fm²" if listing.area_m2 is not None else None
        floor_str = _floor_str(listing.floor_current, listing.floor_total)
        if resolved_deal_type == "sell":
            price_label = "💰 Kopējā cena"
            price_str = format_price(listing.price_total_eur, "€")
            per_m2_str = format_price(listing.price_per_m2_eur, "€/m²")
        elif resolved_deal_type == "rent":
            price_label = "💰 Cena/mēn."
            price_str = format_price(listing.price_monthly_eur, "€/mēn.")
            per_m2_str = None
        else:
            price_label = "💰 Cena"
            price_str = escape(listing.price) if listing.price else None
            per_m2_str = None

        lines: list[str] = [f"<b>{escape(listing.title)}</b>"]
        for line in [
            _opt_line("🏙 Pilsēta", listing.city),
            _opt_line("📍 Rajons", listing.district),
            _opt_line("🚪 Iela", listing.street),
            _opt_line("🛏 Istabas", listing.rooms),
            _opt_line("📐 Platība", area_str),
            _opt_line("🏢 Stāvs", floor_str),
            _opt_line("🧱 Sērija", listing.series),
            _opt_line("🏠 Mājas tips", listing.house_type),
            _opt_line("💶 Cena/m²", per_m2_str),
            _opt_line(price_label, price_str),
        ]:
            if line:
                lines.append(line)
        lines.append(f"🔗 {listing.url}")
        return "\n".join(lines)

    area_str = _format_area_lv(listing.area_m2)
    floor_str = _floor_str(listing.floor_current, listing.floor_total)
    raw_cena = listing.detail_raw_cena or listing.price
    rendered_price = _render_flats_price(raw_cena, resolved_deal_type)
    parsed_labels = list(listing.detail_parsed_labels or [])

    if listing.detail_fetch_ok:
        lines: list[str] = []
        if listing.city:
            lines.append(f"Pilsēta: {escape(str(listing.city))}")
        if listing.district:
            lines.append(f"Rajons: {escape(str(listing.district))}")
        if listing.street:
            lines.append(f"Iela: {escape(str(listing.street))}")
        if listing.rooms is not None:
            lines.append(f"Istabas: {escape(str(listing.rooms))}")
        if area_str:
            lines.append(f"Platība: {escape(area_str)}")
        if floor_str:
            lines.append(f"Stāvs: {escape(floor_str)}")
        if listing.series:
            lines.append(f"Sērija: {escape(str(listing.series))}")
        if listing.house_type:
            lines.append(f"Mājas tips: {escape(str(listing.house_type))}")
        if getattr(listing, "comforts", None):
            lines.append(f"Ērtības: {escape(str(listing.comforts))}")
        if getattr(listing, "cadastral_number", None):
            lines.append(f"Kadastra numurs: {escape(str(listing.cadastral_number))}")
        if rendered_price:
            lines.append(f"Cena: {escape(rendered_price)}")
        lines.append(f"Saite: {escape(listing.url)}")
        template = "flats_detail_lv"
    else:
        parse_error = listing.detail_parse_error or "unknown_detail_error"
        logger.warning(
            "Flats detail fallback listing_id=%s url=%s parse_error=%s",
            listing.external_id,
            listing.url,
            parse_error,
        )
        lines = [f"Sludinājums: {escape(listing.title)}"]
        if listing.price:
            lines.append(f"Cena: {escape(str(listing.price))}")
        lines.append(f"Saite: {escape(listing.url)}")
        template = "fallback"

    logger.info(
        "Flats notification listing_id=%s url=%s detail_fetch_ok=%s parsed_labels=%s "
        "raw_cena=%r rendered_price=%r template=%s",
        listing.external_id,
        listing.url,
        listing.detail_fetch_ok,
        parsed_labels,
        raw_cena,
        rendered_price,
        template,
    )
    return "\n".join(lines)


def format_cars_message(listing: "Listing") -> str:
    """Render cars notifications with full Latvian detail fields when detail fetch succeeds."""
    parsed_fields = list(listing.detail_parsed_labels or [])

    if listing.detail_fetch_ok:
        lines: list[str] = []
        ordered_fields: list[tuple[str, str | None]] = [
            ("Marka", getattr(listing, "car_make", None)),
            ("Izlaiduma gads", getattr(listing, "car_year", None)),
            ("Motors", getattr(listing, "car_engine", None)),
            ("Ātrumkārba", getattr(listing, "car_gearbox", None)),
            ("Nobraukums, km", getattr(listing, "car_mileage_km", None)),
            ("Krāsa", getattr(listing, "car_color", None)),
            ("Virsbūves tips", getattr(listing, "car_body_type", None)),
            ("Tehniskā apskate", getattr(listing, "car_technical_inspection", None)),
            ("Cena", listing.detail_raw_cena or listing.price),
        ]
        for label, value in ordered_fields:
            if value is None or str(value).strip() == "":
                continue
            lines.append(f"{label}: {escape(str(value).strip())}")
        lines.append(f"Saite: {escape(listing.url)}")
        rendered_template = "cars_detail_lv"
    else:
        parse_error = listing.detail_parse_error or "unknown_detail_error"
        fallback_price, fallback_price_source = _cars_fallback_price(listing)
        marka_modelis = _cars_model_fallback(listing)
        logger.warning(
            "Cars detail fallback listing_id=%s url=%s parse_error=%s fallback_price_source=%s final_template=%s",
            listing.external_id,
            listing.url,
            parse_error,
            fallback_price_source,
            "fallback_minimal",
        )
        lines = [
            f"Marka/Modelis: {escape(marka_modelis)}",
            f"Cena: {escape(fallback_price)}",
            f"Saite: {escape(listing.url)}",
        ]
        rendered_template = "fallback_minimal"

    logger.info(
        "Cars notification listing_id=%s url=%s detail_fetch_ok=%s parsed_fields=%s rendered_template=%s",
        listing.external_id,
        listing.url,
        listing.detail_fetch_ok,
        parsed_fields,
        rendered_template,
    )
    return "\n".join(lines)


def format_listing_message(listing: "Listing", search_url: str | None = None) -> str:
    """
    Select and render the appropriate message template.

    For SS.lv flats listings (detected from ``listing.url``), uses
    :func:`format_flats_message` with Latvian detail-table labels.

    For other categories uses ``listing.deal_type`` (inferred from
    *search_url* when the listing's own deal_type is ``'unknown'``).
    Falls back to the generic template when still unknown.
    """
    from app.filters.profiles import detect_profile

    deal_type = listing.deal_type
    if deal_type == "unknown" and search_url:
        deal_type = detect_deal_type(search_url)

    profile = detect_profile(listing.url)
    if profile == "flats":
        return format_flats_message(listing, deal_type=deal_type)
    if profile == "cars" and listing.detail_fetch_ok is not None:
        return format_cars_message(listing)

    if deal_type == "sell":
        return format_sell_message(listing)
    if deal_type == "rent":
        return format_rent_message(listing)
    return format_generic_message(listing)
