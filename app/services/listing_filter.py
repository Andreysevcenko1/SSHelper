"""Local (client-side) listing filter matching.

SS.lv does not reliably apply search filters passed as GET query params
(filters are form-POST + cookie-session based and the endpoint is bot-throttled),
so saved query filters are enforced here against the enriched listing data
before a notification is sent.

Rules:
- Unknown/unsupported filter keys are ignored.
- If listing data required for a check is missing, the check passes
  (we never drop a listing on uncertainty).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.filters.profiles import to_canonical

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ss_parser import Listing

logger = logging.getLogger(__name__)

_FLOAT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _FLOAT_RE.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def _extract_year(value) -> int | None:
    if value is None:
        return None
    m = _YEAR_RE.search(str(value))
    return int(m.group(0)) if m else None


def _listing_price_eur(listing: "Listing") -> float | None:
    from app.services.ss_parser import normalize_price_eur

    if listing.price_total_eur is not None:
        return listing.price_total_eur
    if listing.price_monthly_eur is not None:
        return listing.price_monthly_eur
    return normalize_price_eur(listing.price)


def _option_labels(profile: str, canonical_key: str, raw_value: str) -> list[str]:
    """Localized labels for a select option value, e.g. '494' -> Dīzelis/Дизель/Diesel."""
    try:
        if profile == "cars":
            from app.filters.profiles.cars import OPTION_VALUES
        else:
            return []
    except ImportError:  # pragma: no cover
        return []
    labels = OPTION_VALUES.get(canonical_key, {}).get(str(raw_value))
    return [v for v in labels.values()] if labels else []


def _select_matches(profile: str, canonical_key: str, raw_value: str, listing_text: str | None) -> bool | None:
    """True/False when decidable, None when listing data is missing/unknown."""
    if not listing_text:
        return None
    labels = _option_labels(profile, canonical_key, raw_value)
    if not labels:
        return None
    haystack = listing_text.casefold()
    return any(lbl.casefold() in haystack for lbl in labels)


def listing_matches_filters(
    listing: "Listing",
    filters: dict,
    profile: str | None,
) -> tuple[bool, str | None]:
    """Check *listing* against saved search *filters*.

    Returns ``(matches, reason)`` where *reason* names the first failed
    canonical filter (for logging), or ``None`` when everything matched.
    """
    if not filters or not profile:
        return True, None
    canonical = to_canonical(filters, profile)
    if not canonical:
        return True, None

    price = _listing_price_eur(listing)
    year = _extract_year(getattr(listing, "car_year", None))
    volume = _to_float(getattr(listing, "car_engine", None))

    numeric_checks: list[tuple[str, float | None, bool]] = []
    for key, raw in canonical.items():
        bound = _to_float(raw)
        if bound is None:
            continue
        if key == "price_min":
            numeric_checks.append((key, price, price is None or price >= bound))
        elif key == "price_max":
            numeric_checks.append((key, price, price is None or price <= bound))
        elif key == "year_min":
            numeric_checks.append((key, year, year is None or year >= bound))
        elif key == "year_max":
            numeric_checks.append((key, year, year is None or year <= bound))
        elif key == "volume_min":
            numeric_checks.append((key, volume, volume is None or volume >= bound))
        elif key == "volume_max":
            numeric_checks.append((key, volume, volume is None or volume <= bound))

    for key, actual, ok in numeric_checks:
        if not ok:
            return False, f"{key} (listing={actual})"

    select_sources = {
        "engine_type": getattr(listing, "car_engine", None),
        "gearbox": getattr(listing, "car_gearbox", None),
        "body_type": getattr(listing, "car_body_type", None),
        "color": getattr(listing, "car_color", None),
    }
    for key, listing_text in select_sources.items():
        raw_value = canonical.get(key)
        if raw_value is None:
            continue
        verdict = _select_matches(profile, key, str(raw_value), listing_text)
        if verdict is False:
            return False, f"{key} (listing={listing_text!r})"

    return True, None
