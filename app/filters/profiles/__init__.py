"""Profile registry for category-specific filter schemas.

Usage::

    from app.filters.profiles import get_profile, detect_profile

    profile = get_profile("flats")   # returns the flats module, or None
    name    = detect_profile(url)    # "flats" | "cars" | None
"""

from __future__ import annotations

import re
from types import ModuleType
from urllib.parse import urlparse

from app.filters.profiles import cars, flats

# ---------------------------------------------------------------------------
# Profile name → module
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ModuleType] = {
    "flats": flats,
    "cars":  cars,
}


def get_profile(name: str | None) -> ModuleType | None:
    """Return the profile module for *name*, or ``None`` if unknown."""
    if not name:
        return None
    return _REGISTRY.get(name)


# ---------------------------------------------------------------------------
# URL-path → profile name detection
# ---------------------------------------------------------------------------

# Ordered list of (path-segment-regex, profile-name) pairs.
# The first match wins.
_PROFILE_RULES: list[tuple[re.Pattern[str], str]] = [
    # /real-estate/flats/ or /nekustamais-ipasums/dzivokli/ variants
    (
        re.compile(
            r"/(?:real-estate|nekustamais[_-]ipasums)/(?:flats|dzivokli|apartments)(?:/|$)",
            re.I,
        ),
        "flats",
    ),
    # /transport/cars/ or /transports/auto/
    (re.compile(r"/(?:transport|transports)/(?:cars|auto)(?:/|$)", re.I), "cars"),
]


def detect_profile(url: str) -> str | None:
    """Detect the category profile from a SS.lv URL path.

    Returns one of ``"flats"``, ``"cars"``, or ``None`` (generic/unknown).

    Examples::

        detect_profile("https://ss.lv/lv/real-estate/flats/riga/sell/")  # "flats"
        detect_profile("https://ss.lv/lv/transport/cars/")               # "cars"
        detect_profile("https://ss.lv/lv/services/")                     # None
    """
    try:
        path = urlparse(url).path
    except Exception:
        return None

    for pattern, profile in _PROFILE_RULES:
        if pattern.search(path):
            return profile
    return None


def to_canonical(raw_filters: dict, profile_name: str | None) -> dict[str, str]:
    """Map raw SS.lv filter keys to canonical names using the given profile.

    Keys that are not in the profile's ``RAW_TO_CANONICAL`` mapping are
    silently dropped (they must not appear in the user UI).

    Args:
        raw_filters: dict of raw key → value from the URL query string.
        profile_name: profile name (``"flats"``, ``"cars"``) or ``None``.

    Returns:
        Ordered dict of canonical field name → value.
    """
    profile = get_profile(profile_name)
    if profile is None:
        return {}

    mapping: dict[str, str] = profile.RAW_TO_CANONICAL
    result: dict[str, str] = {}
    for raw_key, value in raw_filters.items():
        canonical = mapping.get(raw_key)
        if canonical and canonical not in result:  # first wins
            result[canonical] = str(value) if not isinstance(value, str) else value
    return result
