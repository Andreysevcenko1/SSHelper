from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.services.formatter import format_listing_message
from app.services.ss_parser import Listing, enrich_listing_from_detail, parse_detail_page
import app.services.group_watcher as group_watcher_module
import app.services.watcher as watcher_module


_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


def _build_enriched_listing(*, fixture_name: str, listing_url: str, deal_type: str, listing_id: str) -> Listing:
    detail_html = _load_fixture(fixture_name)
    detail_data = parse_detail_page(detail_html)
    base = Listing(
        external_id=listing_id,
        title="fixture",
        url=listing_url,
        deal_type=deal_type,
    )
    enriched = enrich_listing_from_detail(base, detail_data)
    return replace(
        enriched,
        detail_fetch_ok=True,
        detail_parsed_labels=list(detail_data.get("parsed_labels") or []),
        detail_raw_cena=detail_data.get("price_raw"),
    )


def test_hiofx_fixture_fields():
    detail = parse_detail_page(_load_fixture("hiofx.html"))
    assert detail["city"] == "Rīga"
    assert detail["district"] == "Klīversala"
    assert detail["street"] == "Raņķa d. 7"
    assert detail["rooms"] == 2
    assert detail["area_m2"] == 42.0
    assert detail["floor_current"] == 2
    assert detail["floor_total"] == 5
    assert detail["series"] == "Hrušč."
    assert detail["house_type"] == "Ķieģeļu-paneļu"
    assert detail["comforts"] == "Parkošanas vieta"
    assert detail["price_raw"] == "430 €/mēn. (10.24 €/m²)"


def test_abnof_fixture_fields():
    detail = parse_detail_page(_load_fixture("abnof.html"))
    assert detail["city"] == "Rīga"
    assert detail["district"] == "centrs"
    assert detail["street"] == "Veru 3"
    assert detail["rooms"] == 3
    assert detail["area_m2"] == 63.0
    assert detail["floor_current"] == 1
    assert detail["floor_total"] == 5
    assert detail["series"] == "P. kara"
    assert detail["house_type"] == "Mūra"
    assert detail["cadastral_number"] == "01009293174"
    assert detail["price_raw"] == "76 000 € (1 206.35 €/m²)"


def test_hiofx_final_message_snapshot_lv():
    listing = _build_enriched_listing(
        fixture_name="hiofx.html",
        listing_url="https://www.ss.lv/msg/lv/real-estate/flats/riga/kliversala/hiofx.html",
        deal_type="rent",
        listing_id="hiofx",
    )
    body = format_listing_message(listing)
    assert body == (
        "Pilsēta: Rīga\n"
        "Rajons: Klīversala\n"
        "Iela: Raņķa d. 7\n"
        "Istabas: 2\n"
        "Platība: 42 m²\n"
        "Stāvs: 2/5\n"
        "Sērija: Hrušč.\n"
        "Mājas tips: Ķieģeļu-paneļu\n"
        "Ērtības: Parkošanas vieta\n"
        "Cena: 430 €/mēn. (10.24 €/m²)\n"
        "Saite: https://www.ss.lv/msg/lv/real-estate/flats/riga/kliversala/hiofx.html"
    )


def test_abnof_final_message_snapshot_lv():
    listing = _build_enriched_listing(
        fixture_name="abnof.html",
        listing_url="https://www.ss.lv/msg/lv/real-estate/flats/riga/centre/abnof.html",
        deal_type="sell",
        listing_id="abnof",
    )
    body = format_listing_message(listing)
    assert body == (
        "Pilsēta: Rīga\n"
        "Rajons: centrs\n"
        "Iela: Veru 3\n"
        "Istabas: 3\n"
        "Platība: 63 m²\n"
        "Stāvs: 1/5\n"
        "Sērija: P. kara\n"
        "Mājas tips: Mūra\n"
        "Kadastra numurs: 01009293174\n"
        "Cena: 76 000 € (1 206.35 €/m²)\n"
        "Saite: https://www.ss.lv/msg/lv/real-estate/flats/riga/centre/abnof.html"
    )


def test_regression_no_malformed_fragments():
    listing = _build_enriched_listing(
        fixture_name="hiofx.html",
        listing_url="https://www.ss.lv/msg/lv/real-estate/flats/riga/kliversala/hiofx.html",
        deal_type="rent",
        listing_id="hiofx",
    )
    body = format_listing_message(listing)
    assert "[Karte]" not in body
    assert "opt[" not in body
    assert "topt[" not in body


def test_group_and_individual_watchers_use_same_flats_rendering():
    listing = _build_enriched_listing(
        fixture_name="hiofx.html",
        listing_url="https://www.ss.lv/msg/lv/real-estate/flats/riga/kliversala/hiofx.html",
        deal_type="rent",
        listing_id="hiofx",
    )
    assert watcher_module.format_listing_message(listing) == group_watcher_module.format_listing_message(listing)
