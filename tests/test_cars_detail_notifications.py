from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import app.services.group_watcher as group_watcher_module
import app.services.watcher as watcher_module
from app.services.formatter import format_listing_message
from app.services.ss_parser import (
    DetailFetchError,
    DetailFetchMeta,
    Listing,
    SSParser,
    enrich_listing_from_detail,
    parse_detail_page,
)


_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


def _build_enriched_car_listing() -> Listing:
    detail_html = _load_fixture("bdpbdp.html")
    detail_data = parse_detail_page(detail_html)
    base = Listing(
        external_id="bdpbdp",
        title="Mercedes Benz E220 Cdi",
        url="https://www.ss.lv/msg/lv/transport/cars/mercedes/e220/bdpbdp.html",
        deal_type="unknown",
    )
    enriched = enrich_listing_from_detail(base, detail_data)
    return replace(
        enriched,
        detail_fetch_ok=True,
        detail_parsed_labels=list(detail_data.get("parsed_labels") or []),
        detail_raw_cena=detail_data.get("price_raw"),
    )


def test_bdpbdp_fixture_fields():
    detail = parse_detail_page(_load_fixture("bdpbdp.html"))
    assert detail["car_make"] == "Mercedes E220"
    assert detail["car_year"] == "2014"
    assert detail["car_engine"] == "2.2 dīzelis"
    assert detail["car_gearbox"] == "Automāts 7 ātrumi"
    assert detail["car_mileage_km"] == "306 000"
    assert detail["car_color"] == "Balta"
    assert detail["car_body_type"] == "Universāls"
    assert detail["car_technical_inspection"] == "02.2027"
    assert detail["price_raw"] == "7 900 €"


def test_bdpbdp_final_message_snapshot_lv():
    listing = _build_enriched_car_listing()
    body = format_listing_message(listing)
    assert body == (
        "Marka: Mercedes E220\n"
        "Izlaiduma gads: 2014\n"
        "Motors: 2.2 dīzelis\n"
        "Ātrumkārba: Automāts 7 ātrumi\n"
        "Nobraukums, km: 306 000\n"
        "Krāsa: Balta\n"
        "Virsbūves tips: Universāls\n"
        "Tehniskā apskate: 02.2027\n"
        "Cena: 7 900 €\n"
        "Saite: https://www.ss.lv/msg/lv/transport/cars/mercedes/e220/bdpbdp.html"
    )


def test_regression_no_truncated_fragments_in_detail_template():
    listing = _build_enriched_car_listing()
    body = format_listing_message(listing)
    assert "izieta tehniska ap" not in body.lower()


def test_group_and_individual_watchers_use_same_cars_rendering():
    listing = _build_enriched_car_listing()
    assert watcher_module.format_listing_message(listing) == group_watcher_module.format_listing_message(listing)


def test_cars_fallback_always_contains_cena_line():
    listing = Listing(
        external_id="57186837",
        title="Skoda Superb",
        url="https://www.ss.lv/msg/lv/transport/cars/skoda/superb/cdbfxb.html",
        deal_type="unknown",
        detail_fetch_ok=False,
        detail_parse_error="timeout",
        detail_raw_cena=None,
        price=None,
    )
    body = format_listing_message(listing)
    assert "Cena: nav norādīta" in body
    assert "Saite: https://www.ss.lv/msg/lv/transport/cars/skoda/superb/cdbfxb.html" in body


def test_altered_structure_extracts_price_and_one_car_field():
    html = """
    <html><body>
      <div>Marka: Audi A6</div>
      <div>Tehniskā apskate: 11.2026</div>
      <div>Cena: 8 500 €</div>
    </body></html>
    """
    detail = parse_detail_page(html)
    assert detail.get("price_raw") == "8 500 €"
    assert detail.get("car_make") == "Audi A6"


@pytest.mark.asyncio
async def test_timeout_fetch_uses_cars_fallback_with_cena():
    parser = SSParser()
    parser._fetch_detail_page_data = AsyncMock(  # type: ignore[method-assign]
        side_effect=DetailFetchError(
            DetailFetchMeta(
                http_status=None,
                content_length=None,
                retry_count=2,
                parse_stage="fetch",
                exception_type="TimeoutError",
                exception_message="request timed out",
            )
        )
    )
    listing = Listing(
        external_id="57186837",
        title="Skoda Superb",
        url="https://www.ss.lv/msg/lv/transport/cars/skoda/superb/cdbfxb.html",
        price="6 999 €",
    )
    enriched = await parser.fetch_and_enrich_listing(listing)
    body = format_listing_message(enriched)
    assert "Cena: 6 999 €" in body
    assert "Marka/Modelis: Skoda Superb" in body
    assert "<b>" not in body
