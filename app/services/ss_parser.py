from dataclasses import dataclass
import logging
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Listing:
    external_id: str
    title: str
    url: str
    price: str | None = None
    city: str | None = None


_ID_RE = re.compile(r"(\d{5,})")

_CATEGORY_MAP = {
    "/transport/": "Транспорт",
    "/real-estate/": "Недвижимость",
    "/animals/": "Животные",
    "/electronics/": "Электроника",
    "/services/": "Услуги",
    "/other/": "Прочее",
    "/clothing/": "Одежда",
    "/garden/": "Сад и огород",
    "/food/": "Еда",
    "/sport/": "Спорт",
    "/business/": "Бизнес",
    "/collect/": "Коллекционирование",
    "/household/": "Дом и быт",
}


def detect_category(url: str) -> str:
    url_lower = url.lower()
    for segment, label in _CATEGORY_MAP.items():
        if segment in url_lower:
            return label
    return "SS.lv"


class SSParser:
    async def fetch_listings(self, search_url: str, limit: int = 20) -> list[Listing]:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html = await response.text()

        return self._parse_listings(html=html, base_url=search_url, limit=limit)

    def _parse_listings(self, html: str, base_url: str, limit: int) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr[id^='tr_']")
        listings: list[Listing] = []

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

            # City is typically in the second-to-last or a specific td column
            city: str | None = None
            city_cell = row.select_one("td.msga2:not(.pp6)")
            if city_cell:
                city_text = city_cell.get_text(strip=True)
                if city_text:
                    city = city_text

            external_id = self._extract_external_id(row.get("id", ""), href)
            if not external_id:
                continue

            listings.append(
                Listing(
                    external_id=external_id,
                    title=title,
                    url=full_url,
                    price=price,
                    city=city,
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
