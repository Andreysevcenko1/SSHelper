"""Profile-aware filter renderer.

Converts a raw filter dict (SS.lv query params) into human-readable bullet
lines, using a category profile for correct labels, option names, and ordering.

Falls back to the legacy ``filter_display_label`` helper for unknown profiles
so that all existing behaviour is preserved.
"""

from __future__ import annotations

import re

from app.filters.profiles import detect_profile, get_profile, to_canonical

# Raw-key pattern – must never appear in user-facing output
_RAW_KEY_RE = re.compile(r"(opt|topt|mid)\[", re.IGNORECASE)


def _label(canonical: str, profile_module, locale: str) -> str:
    """Return the human-readable label for a canonical field."""
    labels: dict = getattr(profile_module, "LABELS", {})
    entry = labels.get(canonical, {})
    return entry.get(locale) or entry.get("ru") or entry.get("en") or canonical


def _display_value(canonical: str, value: str, profile_module, locale: str) -> str:
    """Return the display string for a canonical field value."""
    option_values: dict = getattr(profile_module, "OPTION_VALUES", {})
    if canonical in option_values:
        opt_map = option_values[canonical].get(str(value), {})
        if opt_map:
            return opt_map.get(locale) or opt_map.get("ru") or opt_map.get("en") or value
    return value


def render_canonical_filters(
    raw_filters: dict,
    profile_name: str | None,
    locale: str = "ru",
) -> list[str]:
    """Render filter dict as human-readable bullet lines.

    For known profiles (``"flats"``, ``"cars"``) every raw SS.lv key is
    mapped to a canonical field; unknown keys are silently skipped so that
    raw ``opt[…]`` / ``topt[…]`` strings never appear in the output.

    For unknown profiles the legacy ``filter_display_label`` fallback is used,
    which also guarantees no raw keys in the output.

    Args:
        raw_filters: dict of raw key → value (from ``filters_from_json``).
        profile_name: category profile name or ``None``.
        locale: BCP-47 tag (``"lv"``, ``"ru"``, ``"en"``).

    Returns:
        List of formatted bullet strings like ``"  • Комнат (от): 2"``.
    """
    profile = get_profile(profile_name)

    if profile is not None:
        return _render_profile(raw_filters, profile, locale)

    # Generic fallback – no raw keys guaranteed by filter_display_label
    return _render_generic(raw_filters, locale)


def _render_profile(raw_filters: dict, profile, locale: str) -> list[str]:
    canonical = to_canonical(raw_filters, profile.__name__.rsplit(".", 1)[-1])

    display_order: list[str] = getattr(profile, "DISPLAY_ORDER", [])
    units: dict[str, str] = getattr(profile, "UNITS", {})

    # Sort by display order first, then alphabetically for remaining fields
    order_index = {f: i for i, f in enumerate(display_order)}
    sorted_fields = sorted(
        canonical.items(),
        key=lambda kv: (order_index.get(kv[0], len(display_order)), kv[0]),
    )

    lines: list[str] = []
    for field, value in sorted_fields:
        lbl = _label(field, profile, locale)
        disp = _display_value(field, value, profile, locale)
        unit = units.get(field, "")
        if unit:
            disp = f"{disp} {unit}"
        lines.append(f"  • {lbl}: {disp}")
    return lines


def _render_generic(raw_filters: dict, locale: str) -> list[str]:
    from app.services.filters import filter_display_label

    lines: list[str] = []
    for key, value in raw_filters.items():
        label = filter_display_label(key, locale=locale)
        # Paranoia: ensure no raw key leaked through
        if _RAW_KEY_RE.search(label):
            continue
        if isinstance(value, list):
            disp = ", ".join(str(v) for v in value)
        else:
            disp = str(value)
        lines.append(f"  • {label}: {disp}")
    return lines
