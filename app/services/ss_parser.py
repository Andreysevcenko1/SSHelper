from dataclasses import dataclass, field
import logging
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


@dataclass
class Listing:
    external_id: str
    title: str
    url: str
    price: str | None = None
    city: str | None = None
    photo_urls: list = field(default_factory=list)
    # Real-estate metadata (nullable; populated for apartment listings when available)
    district: str | None = None
    street: str | None = None
    rooms: int | None = None
    area_m2: float | None = None
    floor_current: int | None = None
    floor_total: int | None = None
    house_type: str | None = None
    price_total_eur: float | None = None
    price_per_m2_eur: float | None = None
    price_monthly_eur: float | None = None
    deal_type: str = "unknown"  # "sell" | "rent" | "unknown"
    image_url_hd: str | None = None
    image_url_preview: str | None = None


# ---------------------------------------------------------------------------
# Price normalisation helpers
# ---------------------------------------------------------------------------

_PRICE_UNIT_RE = re.compile(
    r'(?i)(eur|usd|/m[eē]n[eē]?|/month|/мес[яц]*|м²|m²|/m²|/м²)',
)
_PRICE_CURRENCY_RE = re.compile(r'[€$£]')
_PRICE_WHITESPACE_RE = re.compile(r'[\s\u00a0\u202f\u2009\u00b7]')
_PRICE_NON_NUMERIC_RE = re.compile(r'[^\d.,]')


def normalize_price_eur(price_str: str | None) -> float | None:
    """
    Parse a price string like ``'125 000 €'`` or ``'850 €/мес'`` to float.

    Returns ``None`` when *price_str* is ``None``, empty, or unparseable.
    """
    if not price_str:
        return None

    cleaned = _PRICE_CURRENCY_RE.sub('', price_str)
    cleaned = _PRICE_UNIT_RE.sub('', cleaned)
    cleaned = _PRICE_WHITESPACE_RE.sub('', cleaned)
    cleaned = _PRICE_NON_NUMERIC_RE.sub('', cleaned)

    if not cleaned:
        return None

    dot_count = cleaned.count('.')
    comma_count = cleaned.count(',')

    try:
        if dot_count == 0 and comma_count == 0:
            return float(cleaned)
        if dot_count == 1 and comma_count == 0:
            return float(cleaned)
        if comma_count == 1 and dot_count == 0:
            return float(cleaned.replace(',', '.'))
        # Multiple separators → all are thousands separators
        return float(cleaned.replace(',', '').replace('.', ''))
    except ValueError:
        return None


def _parse_price_fields(
    price_str: str | None,
    deal_type: str,
    area_m2: float | None,
) -> tuple[float | None, float | None, float | None]:
    """
    Derive ``(price_total_eur, price_monthly_eur, price_per_m2_eur)`` from a
    raw price string and the listing's deal type.

    For sell listings, also computes ``price_per_m2_eur`` when area is known.
    """
    if not price_str:
        return None, None, None

    numeric = normalize_price_eur(price_str)
    if numeric is None:
        return None, None, None

    price_lower = price_str.lower()
    is_monthly = any(kw in price_lower for kw in ('мес', 'month', 'mēn', '/m'))
    is_per_m2 = any(kw in price_lower for kw in ('м²', 'm²', '/m²'))

    if is_per_m2:
        return None, None, numeric

    if is_monthly or deal_type == 'rent':
        return None, numeric, None

    # Sell / unknown: treat as total price
    per_m2: float | None = None
    if area_m2 and area_m2 > 0:
        per_m2 = round(numeric / area_m2, 2)
    return numeric, None, per_m2


# ---------------------------------------------------------------------------
# Real-estate cell parsing helpers
# ---------------------------------------------------------------------------

_ROOMS_RE = re.compile(r'^\s*(\d{1,2})\s*$')
_AREA_RE = re.compile(r'^\s*(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:m²|м²)?\s*$')
_FLOOR_RE = re.compile(r'^\s*(\d{1,3})\s*/\s*(\d{1,3})\s*$')


def _try_parse_rooms(text: str) -> int | None:
    """Return room count 1–20 if *text* looks like a room count, else ``None``."""
    m = _ROOMS_RE.match(text.strip())
    if m:
        val = int(m.group(1))
        return val if 1 <= val <= 20 else None
    return None


def _try_parse_area(text: str) -> float | None:
    """Return area in m² if *text* looks like an area value (5–2000), else ``None``."""
    m = _AREA_RE.match(text.strip())
    if m:
        val = float(m.group(1).replace(',', '.'))
        return val if 5.0 <= val <= 2000.0 else None
    return None


def _try_parse_floor(text: str) -> tuple[int, int] | None:
    """Return ``(floor_current, floor_total)`` from ``'3/9'`` format, else ``None``."""
    m = _FLOOR_RE.match(text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _parse_realestate_cells(
    row: Tag, title_link: Tag
) -> tuple[int | None, float | None, int | None, int | None]:
    """
    Extract ``(rooms, area_m2, floor_current, floor_total)`` from the data cells
    in a search-result row.

    Skips the price cell (``pp6``) and the description cell (the one that
    contains the listing link).
    """
    rooms: int | None = None
    area_m2: float | None = None
    floor_current: int | None = None
    floor_total: int | None = None

    for cell in row.find_all("td", class_="msga2"):
        cell_classes = cell.get("class", [])
        if "pp6" in cell_classes:
            continue
        # Skip the description cell (contains the anchor link to the listing)
        if cell.find("a", class_="am") or title_link.parent == cell:
            continue
        text = cell.get_text(strip=True)
        if not text:
            continue

        if rooms is None:
            val = _try_parse_rooms(text)
            if val is not None:
                rooms = val
                continue
        if area_m2 is None:
            val = _try_parse_area(text)
            if val is not None:
                area_m2 = val
                continue
        if floor_current is None and floor_total is None:
            result = _try_parse_floor(text)
            if result is not None:
                floor_current, floor_total = result

    return rooms, area_m2, floor_current, floor_total


def _parse_location(
    city_text: str | None,
    title: str,
) -> tuple[str | None, str | None]:
    """
    Try to extract ``(district, street)`` from the description-cell text.

    SS.lv addresses are typically ``'City, District, Street'``.  The title
    (link text) is often the street address.  Returns ``(None, None)`` when
    not enough information is available.
    """
    if not city_text:
        return None, None

    parts = [p.strip() for p in city_text.split(',') if p.strip()]

    if len(parts) >= 3:
        # "Rīga, Centrs, Barona iela 15" → district=Centrs, street=Barona iela 15
        return parts[1], ', '.join(parts[2:])

    if len(parts) == 2:
        # "Rīga, Centrs" → district=Centrs, use title as street candidate
        street = title if title and title not in parts else None
        return parts[1], street

    # Single part — not enough to split
    return None, None


_ID_RE = re.compile(r"(\d{5,})")

_CATEGORY_MAP = {
    "/transport/": "transport",
    "/real-estate/": "real-estate",
    "/animals/": "animals",
    "/electronics/": "electronics",
    "/services/": "services",
    "/other/": "other",
    "/clothing/": "clothing",
    "/garden/": "garden",
    "/food/": "food",
    "/sport/": "sport",
    "/business/": "business",
    "/collect/": "collect",
    "/household/": "household",
}


def detect_category(url: str) -> str:
    url_lower = url.lower()
    for segment, label in _CATEGORY_MAP.items():
        if segment in url_lower:
            return label
    return "ss.lv"


class SSParser:
    async def fetch_listings(self, search_url: str, limit: int = 20) -> list[Listing]:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html = await response.text()

        return self._parse_listings(html=html, base_url=search_url, limit=limit)

    def _parse_listings(self, html: str, base_url: str, limit: int) -> list[Listing]:
        # Import here to avoid a module-level circular dependency
        from app.services.formatter import detect_deal_type, upgrade_image_url

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr[id^='tr_']")
        listings: list[Listing] = []

        # Derive deal_type once per page from the search URL
        deal_type = detect_deal_type(base_url)

        for row in rows:
            link_tag = row.select_one("a.am") or row.select_one("a[href]")
            if link_tag is None:
                continue

            href = (link_tag.get("href") or "").strip()
            if not href:
                continue

            full_url = urljoin(base_url, href)
            title = link_tag.get_text(strip=True) or "Без названия"
            price_cell = row.select_one("td.msga2-o.pp6")
            price = price_cell.get_text(" ", strip=True) if price_cell else None

            # City / address is in the first td.msga2 cell (not the price cell)
            city: str | None = None
            city_cell = row.select_one("td.msga2:not(.pp6)")
            if city_cell:
                city_text = city_cell.get_text(strip=True)
                if city_text:
                    city = city_text

            # Parse district / street from the full address text
            district, street = _parse_location(city, title)

            # Extract thumbnail photo; also derive HD URL
            photo_urls: list[str] = []
            image_url_hd: str | None = None
            image_url_preview: str | None = None

            img_tag = row.select_one("img[src]")
            if img_tag:
                img_src = (img_tag.get("src") or "").strip()
                if img_src and not img_src.endswith((".gif",)):
                    photo_url = urljoin(base_url, img_src)
                    photo_urls.append(photo_url)
                    image_url_preview = photo_url
                    hd = upgrade_image_url(photo_url)
                    if hd != photo_url:
                        image_url_hd = hd
                        logger.debug(
                            "Parser: image upgraded to HD for row %s → %s",
                            row.get("id", "?"), hd,
                        )
                    else:
                        logger.debug(
                            "Parser: no HD variant detected for row %s → %s",
                            row.get("id", "?"), photo_url,
                        )

            # Best-effort extraction of real-estate data cells
            rooms, area_m2, floor_current, floor_total = _parse_realestate_cells(
                row, link_tag
            )

            # Numeric price breakdown
            price_total_eur, price_monthly_eur, price_per_m2_eur = _parse_price_fields(
                price, deal_type, area_m2
            )

            external_id = self._extract_external_id(row.get("id", ""), href)
            if not external_id:
                continue

            logger.debug(
                "Listing parsed: id=%s deal_type=%s district=%r rooms=%s "
                "area=%s price_total=%s price_monthly=%s",
                external_id, deal_type, district, rooms, area_m2,
                price_total_eur, price_monthly_eur,
            )

            listings.append(
                Listing(
                    external_id=external_id,
                    title=title,
                    url=full_url,
                    price=price,
                    city=city,
                    photo_urls=photo_urls,
                    district=district,
                    street=street,
                    rooms=rooms,
                    area_m2=area_m2,
                    floor_current=floor_current,
                    floor_total=floor_total,
                    price_total_eur=price_total_eur,
                    price_per_m2_eur=price_per_m2_eur,
                    price_monthly_eur=price_monthly_eur,
                    deal_type=deal_type,
                    image_url_hd=image_url_hd,
                    image_url_preview=image_url_preview,
                )
            )
            if len(listings) >= limit:
                break

        return listings

    @staticmethod
    def _extract_external_id(row_id: str, href: str) -> str | None:
        for source in (row_id, href):
            match = _ID_RE.search(source)
            if match:
                return match.group(1)
        return None

    async def discover_available_filters(self, search_url: str) -> dict:
        """
        Fetch *search_url*, parse all HTML form fields and return a schema dict.

        Each key is the field ``name`` attribute; the value is a dict with:
        - ``label``   – human-readable label (best-effort)
        - ``type``    – "select" | "text" | "checkbox" | "radio" | "range" | "hidden" | …
        - ``options`` – list of ``{value, text, selected}`` for select/radio fields
        - ``current_value`` – currently selected / default value
        """
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html = await response.text()

        schema = _parse_filter_schema(html)
        logger.info("discover_available_filters: found %d fields for %s", len(schema), search_url)
        return schema


def _find_label(soup: BeautifulSoup, field: Tag) -> str:
    """Try to find the human-readable label for a form field."""
    field_id = field.get("id", "")
    if field_id:
        label_tag = soup.find("label", {"for": field_id})
        if label_tag:
            return label_tag.get_text(strip=True)
    parent = field.parent
    if parent:
        label_tag = parent.find("label")
        if label_tag:
            return label_tag.get_text(strip=True)
    return field.get("name", "")


def _parse_filter_schema(html: str) -> dict:
    """Parse all form fields in *html* and return a schema dict."""
    soup = BeautifulSoup(html, "html.parser")
    schema: dict[str, dict] = {}

    for form in soup.find_all("form"):
        for field in form.find_all(["input", "select", "textarea"]):
            name = (field.get("name") or "").strip()
            if not name:
                continue

            tag_name: str = field.name  # type: ignore[assignment]
            if tag_name == "input":
                field_type = (field.get("type") or "text").lower()
            elif tag_name == "select":
                field_type = "select"
            else:
                field_type = "textarea"

            entry: dict = {
                "name": name,
                "label": _find_label(soup, field),
                "type": field_type,
                "current_value": field.get("value", ""),
                "options": [],
            }

            if field_type == "select":
                options = []
                for opt in field.find_all("option"):
                    opt_value = opt.get("value", "")
                    is_selected = opt.has_attr("selected")
                    options.append({
                        "value": opt_value,
                        "text": opt.get_text(strip=True),
                        "selected": is_selected,
                    })
                entry["options"] = options
                selected_opts = [o for o in options if o["selected"]]
                entry["current_value"] = selected_opts[0]["value"] if selected_opts else ""

            elif field_type == "checkbox":
                entry["current_value"] = field.has_attr("checked")

            elif field_type == "radio":
                entry["options"] = [{"value": field.get("value", ""), "checked": field.has_attr("checked")}]
                entry["current_value"] = field.get("value", "") if field.has_attr("checked") else ""

            # If the field name already seen, merge radio options
            if name in schema and field_type == "radio":
                schema[name]["options"].extend(entry["options"])
                if field.has_attr("checked"):
                    schema[name]["current_value"] = entry["current_value"]
            else:
                schema[name] = entry

    return schema
