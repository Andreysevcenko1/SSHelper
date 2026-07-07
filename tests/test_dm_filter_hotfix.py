import re
from types import SimpleNamespace

import pytest

from app.bot.handlers import filter_cmds
from app.bot.handlers.filter_cmds import _format_edit_prompt, _resolve_field_options, _sorted_fields
from app.bot.handlers.menu import _format_search_details
from app.bot.keyboards.filters import filter_fields_kb
from app.filters.renderer import render_canonical_filters

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
    assert labels.count("Год (от)") == 1
    assert labels.count("Год (до)") == 1


def test_legacy_filters_render_correctly_for_cars_profile():
    raw = {"pr_min": "5000", "pr_max": "9000", "opt[14]": "BMW", "opt[4]": "2"}
    lines = render_canonical_filters(raw, "cars", locale="ru")
    joined = " ".join(lines)
    assert "Марка" in joined and "BMW" in joined
    assert "Тип топлива" in joined and "Дизель" in joined
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
    assert source == "model_scoped_by_brand"
    texts = [o["display_text"] for o in options]
    assert "X5" in texts and "X3" in texts
    assert "Дизель" not in texts and "Универсал" not in texts
