from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import app.services.group_watcher as group_watcher_module
import app.services.watcher as watcher_module
from app.services.formatter import format_listing_message
from app.services.ss_parser import Listing, enrich_listing_from_detail, parse_detail_page


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
