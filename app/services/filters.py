import hashlib
import json
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


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
