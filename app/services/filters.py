import hashlib
import json
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.i18n import get_text
from app.services.filter_registry import registry_reverse_map

logger = logging.getLogger(__name__)

_RE_RAW_SS_KEY = re.compile(r"^(?:opt|topt)\[.*\]$", re.IGNORECASE)
_RE_RAW_SS_KEY_EXT = re.compile(r"^(?:opt|topt|mid)\[.*\]$", re.IGNORECASE)
_REGISTRY_MAP = registry_reverse_map()


def _normalize_query_key(key: str) -> str:
    return re.sub(r"\s+", "", key.strip()).lower()


def _resolve_localized_text(text_key: str, locale: str) -> str:
    preferred = locale if locale in {"ru", "lv", "en"} else "en"
    text = get_text(text_key, preferred)
    if text != text_key:
        return text
    text_en = get_text(text_key, "en")
    if text_en != text_key:
        return text_en
    generic_key = {
        "ru": "filter_lbl_parameter",
        "lv": "filter_lbl_parameter",
        "en": "filter_lbl_parameter",
    }[preferred]
    return get_text(generic_key, preferred)


def canonical_filter_key(raw_key: str) -> str | None:
    normalized = _normalize_query_key(raw_key)
    spec = _REGISTRY_MAP.get(normalized)
    canonical = spec.canonical_key if spec else None
    logger.debug("filter_key_map: raw_key=%r -> canonical_key=%r", raw_key, canonical)
    return canonical


def normalize_filter_keys_for_display(
    filters: dict[str, str | list[str]],
) -> dict[str, str | list[str]]:
    """Return canonicalized key dict for display purposes (no behavior changes)."""
    result: dict[str, str | list[str]] = {}
    for raw_key, value in filters.items():
        canonical = canonical_filter_key(raw_key) or _normalize_query_key(raw_key)
        result[canonical] = value
    return result


def filter_display_label(
    key: str,
    schema: dict | None = None,
    locale: str = "lv",
) -> str:
    """Return localized, user-friendly label for a filter key in DM UI."""
    normalized = _normalize_query_key(key)
    spec = _REGISTRY_MAP.get(normalized)
    if spec is not None:
        resolved = _resolve_localized_text(spec.label_i18n_key, locale)
        logger.debug(
            "filter_label_resolve: canonical_key=%s locale=%s -> label=%r",
            spec.canonical_key,
            locale,
            resolved,
        )
        return resolved

    if schema:
        info = schema.get(key) or schema.get(normalized)
        if info:
            lbl = re.sub(r"\s+", " ", str(info.get("label") or "").strip())
            if lbl and not _RE_RAW_SS_KEY_EXT.search(lbl):
                logger.debug(
                    "filter_label_resolve: canonical_key=%s locale=%s -> label=%r (schema)",
                    normalized,
                    locale,
                    lbl,
                )
                return lbl

    # Safety net: unresolved or raw SS keys must never be shown to users.
    resolved = _resolve_localized_text("filter_lbl_parameter", locale)
    logger.debug(
        "filter_label_resolve: canonical_key=%s locale=%s -> label=%r (generic)",
        normalized,
        locale,
        resolved,
    )
    return resolved


def extract_filters_from_url(url: str) -> dict[str, str | list[str]]:
    """Extract query parameters from a URL as a normalised dict."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=False, encoding="utf-8", errors="replace")
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
