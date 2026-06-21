import hashlib
import json
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.i18n import get_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SS.lv raw-key patterns used for human-readable display labels
# ---------------------------------------------------------------------------
_RE_OPT = re.compile(r"^(?:topt|opt)\[(\d*)\]$", re.IGNORECASE)
_RE_TOPT_RANGE = re.compile(r"^topt\[(\d+)\]\[(min|max)\]$", re.IGNORECASE)
_RE_MID = re.compile(r"^mid\[([^\]]*)\]$", re.IGNORECASE)
_RE_PRICE_MIN = re.compile(r"^(?:pr_?min|price_?(?:min|from))$", re.IGNORECASE)
_RE_PRICE_MAX = re.compile(r"^(?:pr_?max|price_?(?:max|to))$", re.IGNORECASE)

# SS.lv numeric ID for the price range topt field (topt[15][min/max])
_PRICE_TOPT_ID = "15"


def filter_display_label(
    key: str,
    schema: dict | None = None,
    locale: str = "lv",
) -> str:
    """Return a human-readable display label for a raw SS.lv filter key.

    Priority:
    1. ``schema[key]["label"]`` when schema is provided.
    2. Pattern-based i18n fallbacks for common SS.lv key shapes
       (``opt[N]``/``topt[N]`` → "Фильтр #N", ``mid[N]`` → "Район #N",
       ``pr_min`` → "Цена от", ``pr_max`` → "Цена до").
    3. Generic cleanup: remove brackets, replace underscores with spaces.

    The raw key is **never** returned as-is when it looks like an SS.lv
    internal parameter (i.e. contains ``[`` or ``]``).

    Args:
        key: Raw SS.lv filter parameter name.
        schema: Optional dict mapping key → ``{"label": ..., "options": ...}``.
        locale: BCP-47 language tag used for i18n fallback strings.
    """
    resolved: str

    # 1. Schema lookup
    if schema:
        info = schema.get(key)
        if info:
            lbl = (info.get("label") or "").strip()
            if lbl:
                resolved = lbl
                logger.debug(
                    "filter_display_label: key=%r locale=%s → %r (schema)",
                    key, locale, resolved,
                )
                return resolved

    # 2. Pattern-based i18n fallbacks
    if _RE_PRICE_MIN.match(key):
        resolved = get_text("filter_lbl_price_from", locale)
        logger.debug(
            "filter_display_label: key=%r locale=%s → %r (price_min pattern)",
            key, locale, resolved,
        )
        return resolved

    if _RE_PRICE_MAX.match(key):
        resolved = get_text("filter_lbl_price_to", locale)
        logger.debug(
            "filter_display_label: key=%r locale=%s → %r (price_max pattern)",
            key, locale, resolved,
        )
        return resolved

    m = _RE_TOPT_RANGE.match(key)
    if m:
        n, bound = m.group(1), m.group(2).lower()
        if n == _PRICE_TOPT_ID:
            text_key = (
                "filter_lbl_topt_price_min" if bound == "min" else "filter_lbl_topt_price_max"
            )
            resolved = get_text(text_key, locale)
        else:
            suffix = get_text(
                "filter_lbl_range_min" if bound == "min" else "filter_lbl_range_max", locale
            )
            base = get_text("filter_lbl_opt", locale)
            resolved = f"{base} #{n}: {suffix}"
        logger.debug(
            "filter_display_label: key=%r locale=%s → %r (topt range pattern)",
            key, locale, resolved,
        )
        return resolved

    m = _RE_OPT.match(key)
    if m:
        n = m.group(1)
        base = get_text("filter_lbl_opt", locale)
        resolved = f"{base} #{n}" if n else base
        logger.debug(
            "filter_display_label: key=%r locale=%s → %r (opt pattern)",
            key, locale, resolved,
        )
        return resolved

    m = _RE_MID.match(key)
    if m:
        n = m.group(1)
        base = get_text("filter_lbl_district", locale)
        resolved = f"{base} #{n}" if n else base
        logger.debug(
            "filter_display_label: key=%r locale=%s → %r (mid pattern)",
            key, locale, resolved,
        )
        return resolved

    # 3. Generic cleanup: drop brackets, underscores → spaces
    cleaned = re.sub(r"[\[\]]", "", key).replace("_", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    resolved = cleaned or key
    logger.debug(
        "filter_display_label: key=%r locale=%s → %r (generic cleanup)",
        key, locale, resolved,
    )
    return resolved


def extract_filters_from_url(url: str) -> dict[str, str | list[str]]:
    """Extract query parameters from a URL as a normalised dict."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=False)
    result: dict[str, str | list[str]] = {}
    for key, values in params.items():
        result[key] = values[0] if len(values) == 1 else values
    return result


def normalize_filters(filters: dict) -> dict[str, str | list[str]]:
    """Normalise filters: sort keys, trim whitespace, drop empty values."""
    normalized: dict[str, str | list[str]] = {}
    for key, value in filters.items():
        key = key.strip()
        if not key:
            continue
        if isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
            if cleaned:
                normalized[key] = cleaned if len(cleaned) > 1 else cleaned[0]
        else:
            cleaned_val = str(value).strip()
            if cleaned_val:
                normalized[key] = cleaned_val
    return dict(sorted(normalized.items()))


def base_url_without_query(url: str) -> str:
    """Return the URL stripped of query string and fragment."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


def build_effective_url(base_url: str, filters: dict) -> str:
    """Reconstruct a full URL from a base URL and a filters dict."""
    parsed = urlparse(base_url)
    params: list[tuple[str, str]] = []
    for key, value in filters.items():
        if isinstance(value, list):
            for v in value:
                params.append((key, v))
        else:
            params.append((key, str(value)))
    return urlunparse(parsed._replace(query=urlencode(params)))


def stable_filters_hash(filters: dict) -> str:
    """Return a SHA-256 hex digest of the normalised filters for deduplication."""
    serialized = json.dumps(filters, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def filters_to_json(filters: dict) -> str | None:
    """Serialise a filters dict to a JSON string, or None if empty."""
    if not filters:
        return None
    return json.dumps(filters, ensure_ascii=False)


def filters_from_json(json_str: str | None) -> dict:
    """Deserialise a JSON string back to a filters dict."""
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}
