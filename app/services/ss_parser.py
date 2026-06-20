from dataclasses import dataclass
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup


@dataclass(slots=True)
class Listing:
    external_id: str
    title: str
    url: str
    price: str | None = None


_ID_RE = re.compile(r"(\\d{5,})")


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

            external_id = self._extract_external_id(row.get("id", ""), href)
            if not external_id:
                continue

            listings.append(Listing(external_id=external_id, title=title, url=full_url, price=price))
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
