import re
from types import SimpleNamespace

import pytest

from app.bot.handlers import filter_cmds
from app.bot.handlers.filter_cmds import (
    _extract_brand_slug_options_from_html,
    _format_edit_prompt,
    _resolve_field_options,
    _rewrite_cars_brand_slug_in_url,
    _sorted_fields,
)
from app.bot.handlers.menu import _format_search_details
from app.bot.keyboards.filters import filter_fields_kb
from app.filters.renderer import render_canonical_filters
from app.services.filter_registry import cars_registry_by_canonical_key

_RAW_KEY_RE = re.compile(r"(opt|topt)\[", re.IGNORECASE)


def test_edit_prompt_is_localized_and_no_raw_tokens_ru():
    field_info = {"label": "opt[17]", "type": "number", "options": []}
    text = _format_edit_prompt(
        lang="ru",
        field_name="topt[17][min]",
        field_info=field_info,
        current_value="5000",
        profile="cars",
    )
    assert "Изменение фильтра" in text
    assert "Цена" in text
    assert "5000" in text
    assert not _RAW_KEY_RE.search(text)


def test_edit_prompt_localization_lv_en():
    field_info = {"label": "", "type": "number", "options": []}
    text_lv = _format_edit_prompt(
        lang="lv",
        field_name="topt[17][min]",
        field_info=field_info,
        current_value="5000",
        profile="cars",
    )
    text_en = _format_edit_prompt(
        lang="en",
        field_name="topt[17][min]",
        field_info=field_info,
        current_value="5000",
        profile="cars",
    )
    assert "Filtra maiņa" in text_lv
    assert "Editing filter" in text_en
    assert not _RAW_KEY_RE.search(text_lv)
    assert not _RAW_KEY_RE.search(text_en)


def test_filter_fields_page_2_has_no_raw_labels():
    schema = {
        f"opt[{i}]": {"label": "", "type": "select", "options": [{"value": "1", "text": "x"}]}
        for i in range(1, 25)
    }
    fields = _sorted_fields(schema, lang="ru", profile="cars")
    kb = filter_fields_kb(search_id=1, fields=fields, page=1, lang="ru")
    for row in kb.inline_keyboard:
        for button in row:
            if button.text:
                assert not _RAW_KEY_RE.search(button.text)


def test_filter_fields_dedup_year_min_max_once():
    schema = {
        "topt[8][min]": {"label": "", "type": "text", "options": []},
        "topt[18][min]": {"label": "", "type": "text", "options": []},
        "topt[8][max]": {"label": "", "type": "text", "options": []},
        "topt[18][max]": {"label": "", "type": "text", "options": []},
    }
    fields = _sorted_fields(schema, lang="ru", profile="cars")
    labels = [label for _idx, _name, label in fields]
    assert labels.count("Год от") == 1
    assert labels.count("Год до") == 1


def test_cars_dm_registry_has_exact_semantic_order():
    specs = sorted(cars_registry_by_canonical_key().values(), key=lambda s: s.order)
    assert [s.canonical_key for s in specs] == [
        "price_min",
        "price_max",
        "year_min",
        "year_max",
        "volume_min",
        "volume_max",
        "engine_type",
        "gearbox",
        "body_type",
        "color",
        "brand",
        "model",
    ]


def test_brand_slug_url_rewrite_for_saab():
    url = "https://www.ss.lv/lv/transport/cars/?topt[17][min]=5000"
    rewritten = _rewrite_cars_brand_slug_in_url(url, "saab")
    assert "/transport/cars/saab/" in rewritten
    assert "topt%5B17%5D%5Bmin%5D=5000" in rewritten or "topt[17][min]=5000" in rewritten


def test_extract_brand_slugs_contains_known_brands():
    html = """
    <a href="/lv/transport/cars/bmw/">BMW</a>
    <a href="/lv/transport/cars/mercedes/">Mercedes</a>
    <a href="/lv/transport/cars/saab/">Saab</a>
    """
    options = _extract_brand_slug_options_from_html(html, "lv")
    values = {o["value"] for o in options}
    assert {"bmw", "mercedes", "saab"}.issubset(values)


def test_legacy_filters_render_correctly_for_cars_profile():
    raw = {"pr_min": "5000", "pr_max": "9000", "opt[14]": "BMW", "opt[4]": "2"}
    lines = render_canonical_filters(raw, "cars", locale="ru")
    joined = " ".join(lines)
    assert "Марка" in joined and "BMW" in joined
    assert "Двигатель" in joined and "Дизель" in joined
    assert "Цена" in joined
    assert not _RAW_KEY_RE.search(joined)


def test_search_details_hides_query_and_keeps_localized_filters():
    search = SimpleNamespace(
        id=1,
        title="transport/cars",
        is_active=True,
        url="https://www.ss.lv/lv/transport/cars/?opt[14]=BMW&topt[17][min]=5000",
        effective_url="https://www.ss.lv/lv/transport/cars/?opt[14]=BMW&topt[17][min]=5000",
        category_profile="cars",
    )
    text = _format_search_details(search, {"opt[14]": "BMW", "topt[17][min]": "5000"}, "ru")
    assert "https://www.ss.lv/lv/transport/cars/" in text
    assert "opt[" not in text and "topt[" not in text
    assert "Марка" in text and "Цена" in text


def test_ru_screen_has_no_latvian_fragments_for_known_values():
    search = SimpleNamespace(
        id=7,
        title="transport/cars",
        is_active=True,
        url="https://www.ss.lv/lv/transport/cars/",
        effective_url="https://www.ss.lv/lv/transport/cars/",
        category_profile="cars",
    )
    text = _format_search_details(search, {"opt[4]": "2", "opt[3]": "2"}, "ru")
    assert "Дизель" in text and "Универсал" in text
    assert "Dīzelis" not in text and "Universāls" not in text


@pytest.mark.asyncio
async def test_model_requires_brand_first_message():
    field_info = {"label": "", "type": "select", "options": [{"value": "1", "text": "A4"}]}
    options, message, source = await _resolve_field_options(
        field_name="opt[15]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={},
        profile="cars",
        lang="ru",
        schema={"opt[15]": field_info},
    )
    assert options == []
    assert "Сначала выберите марку" in message
    assert source == "missing_brand"


@pytest.mark.asyncio
async def test_model_options_scoped_by_selected_brand(monkeypatch):
    async def _fake_schema(_url: str):
        return {
            "opt[15]": {
                "label": "Модель",
                "type": "select",
                "options": [
                    {"value": "x5", "text": "X5"},
                    {"value": "x3", "text": "X3"},
                ],
            }
        }

    monkeypatch.setattr(filter_cmds, "_get_schema", _fake_schema)
    field_info = {"label": "", "type": "select", "options": []}
    options, message, source = await _resolve_field_options(
        field_name="opt[15]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={"opt[14]": "BMW"},
        profile="cars",
        lang="ru",
        schema={"opt[15]": field_info},
    )
    assert message is None
    assert source == "model"
    texts = [o["display_text"] for o in options]
    assert "X5" in texts and "X3" in texts
    assert "Дизель" not in texts and "Универсал" not in texts


@pytest.mark.asyncio
async def test_brand_options_use_slug_source_not_fuel(monkeypatch):
    async def _fake_brand_options(_search_url: str, _lang: str):
        return [
            {"value": "bmw", "text": "BMW"},
            {"value": "saab", "text": "Saab"},
        ]

    monkeypatch.setattr(filter_cmds, "_fetch_brand_slug_options", _fake_brand_options)
    field_info = {
        "label": "",
        "type": "select",
        "options": [{"value": "2", "text": "Дизель"}],  # wrong schema source, must be ignored
    }
    options, message, source = await _resolve_field_options(
        field_name="opt[14]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={},
        profile="cars",
        lang="ru",
        schema={"opt[14]": field_info},
    )
    assert message is None
    assert source == "brand"
    texts = [o["display_text"] for o in options]
    assert "BMW" in texts and "Saab" in texts
    assert "Дизель" not in texts and "Универсал" not in texts


@pytest.mark.asyncio
async def test_body_options_are_not_gearbox(monkeypatch):
    field_info = {"label": "", "type": "select", "options": [{"value": "2", "text": "Универсал"}]}
    options, message, source = await _resolve_field_options(
        field_name="opt[3]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={"opt[14]": "BMW"},
        profile="cars",
        lang="ru",
        schema={"opt[3]": field_info},
    )
    assert message is None
    assert source == "body_type"
    texts = [o["display_text"] for o in options]
    assert "Универсал" in texts and "Автомат" not in texts


@pytest.mark.asyncio
async def test_gearbox_options_are_not_body(monkeypatch):
    field_info = {"label": "", "type": "select", "options": [{"value": "2", "text": "Автомат"}]}
    options, message, source = await _resolve_field_options(
        field_name="opt[5]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={"opt[14]": "BMW"},
        profile="cars",
        lang="ru",
        schema={"opt[5]": field_info},
    )
    assert message is None
    assert source == "gearbox"
    texts = [o["display_text"] for o in options]
    assert "Автомат" in texts and "Универсал" not in texts


@pytest.mark.asyncio
async def test_engine_options_are_engine_domain(monkeypatch):
    field_info = {"label": "", "type": "select", "options": [{"value": "2", "text": "Дизель"}]}
    options, message, source = await _resolve_field_options(
        field_name="opt[4]",
        field_info=field_info,
        search_url="https://www.ss.lv/lv/transport/cars/",
        current_filters={"opt[14]": "BMW"},
        profile="cars",
        lang="ru",
        schema={"opt[4]": field_info},
    )
    assert message is None
    assert source == "engine_type"
    texts = [o["display_text"] for o in options]
    assert "Дизель" in texts and "Автомат" not in texts
