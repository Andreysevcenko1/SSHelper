"""P0 blocking tests for the strict DM cars filter routing pipeline.

Covers: canonical registry integrity, callback->canonical routing,
input-mode guards, brand slug provider fallback/exclusions, locale
consistency, page dedup, per-key prompt templates, legacy compatibility.
"""
import re
from types import SimpleNamespace

import pytest

from app.bot.callbacks import FilterEditCB, FilterOptCB
from app.bot.handlers import filter_cmds
from app.bot.handlers.filter_cmds import (
    _extract_brand_slug_options_from_html,
    _fallback_brand_slug_options,
    _format_edit_prompt,
    _input_mode_for,
    _resolve_field_by_canonical,
    _sorted_fields,
    cb_filter_edit_field,
)
from app.bot.keyboards.filters import filter_fields_kb, filter_options_kb
from app.bot.states import EditFilterFSM
from app.i18n import get_text
from app.services.filter_registry import (
    CARS_DM_FILTER_REGISTRY,
    INPUT_MODE_NUMERIC,
    INPUT_MODE_SELECT,
    SS_PARAM_MODE_PATH,
)
from app.services.filters import filter_display_label

_RAW_KEY_RE = re.compile(r"(opt|topt)\[", re.IGNORECASE)

# Mirrors the real SS.lv cars schema keys/values (probed live).
_FULL_CARS_SCHEMA = {
    "topt[8][min]": {"label": "", "type": "text", "options": []},
    "topt[8][max]": {"label": "", "type": "text", "options": []},
    "topt[18][min]": {"label": "", "type": "text", "options": []},
    "topt[18][max]": {"label": "", "type": "text", "options": []},
    "topt[15][min]": {"label": "", "type": "text", "options": []},
    "topt[15][max]": {"label": "", "type": "text", "options": []},
    "opt[34]": {"label": "", "type": "select", "options": [{"value": "494", "text": "Dīzelis"}]},
    "opt[35]": {"label": "", "type": "select", "options": [{"value": "497", "text": "Automāts"}]},
    "opt[32]": {"label": "", "type": "select", "options": [{"value": "483", "text": "Universāls"}]},
    "opt[17]": {"label": "", "type": "select", "options": [{"value": "6318", "text": "Balta"}]},
}


# ------------------------------------------------------------------ #
# Fakes for handler-level interaction tests                            #
# ------------------------------------------------------------------ #


class FakeState:
    def __init__(self, data=None):
        self._data = dict(data or {})
        self.state = None

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self._data = {}
        self.state = None


class FakeMessage:
    def __init__(self):
        self.edits = []
        self.message_id = 100

    async def edit_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))


class FakeCallback:
    def __init__(self):
        self.message = FakeMessage()
        self.from_user = SimpleNamespace(id=1, language_code="ru")
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


def _cars_state_data():
    return {
        "schema": dict(_FULL_CARS_SCHEMA),
        "sid": 1,
        "profile": "cars",
        "current_filters": {},
        "search_url": "https://www.ss.lv/lv/transport/cars/",
        "field_order": list(_FULL_CARS_SCHEMA.keys()),
    }


@pytest.fixture()
def ru_lang(monkeypatch):
    monkeypatch.setattr(filter_cmds, "get_user_lang", lambda *_a, **_k: "ru")


# ------------------------------------------------------------------ #
# A. Mapping integrity                                                 #
# ------------------------------------------------------------------ #


def test_registry_input_modes_are_numeric_or_select_only():
    numeric = {"price_min", "price_max", "year_min", "year_max", "volume_min", "volume_max"}
    select = {"engine_type", "gearbox", "body_type", "color", "brand", "model"}
    for spec in CARS_DM_FILTER_REGISTRY:
        assert spec.input_mode in {INPUT_MODE_NUMERIC, INPUT_MODE_SELECT}
        if spec.canonical_key in numeric:
            assert spec.input_mode == INPUT_MODE_NUMERIC, spec.canonical_key
        if spec.canonical_key in select:
            assert spec.input_mode == INPUT_MODE_SELECT, spec.canonical_key


def test_registry_select_sources_not_cross_wired():
    expected = {
        "engine_type": "engine_type",
        "gearbox": "gearbox",
        "body_type": "body_type",
        "color": "color",
        "brand": "brand",
        "model": "model",
    }
    for spec in CARS_DM_FILTER_REGISTRY:
        if spec.canonical_key in expected:
            assert spec.option_provider_id == expected[spec.canonical_key]


def test_brand_is_path_param_mode():
    brand = next(s for s in CARS_DM_FILTER_REGISTRY if s.canonical_key == "brand")
    assert brand.ss_param_mode == SS_PARAM_MODE_PATH


# ------------------------------------------------------------------ #
# B. Callback routing: canonical key embedded in payload               #
# ------------------------------------------------------------------ #


def test_fields_kb_embeds_canonical_keys_in_callbacks():
    fields = _sorted_fields(_FULL_CARS_SCHEMA, lang="ru", profile="cars")
    by_ck: dict[str, str] = {}
    for page in range(0, 2):
        kb = filter_fields_kb(search_id=1, fields=fields, page=page, lang="ru")
        for row in kb.inline_keyboard:
            for button in row:
                if button.callback_data and button.callback_data.startswith("fe:"):
                    cb = FilterEditCB.unpack(button.callback_data)
                    if cb.ck:
                        by_ck[cb.ck] = button.text
    assert by_ck.get("price_min", "").startswith("Цена от")
    assert by_ck.get("body_type", "").startswith("Тип кузова")
    assert by_ck.get("gearbox", "").startswith("Коробка передач")
    assert by_ck.get("brand", "").startswith("Марка")


def test_resolve_field_by_canonical_maps_to_correct_raw_key():
    name, _info = _resolve_field_by_canonical(_FULL_CARS_SCHEMA, "body_type")
    assert name == "opt[32]"
    name, _info = _resolve_field_by_canonical(_FULL_CARS_SCHEMA, "gearbox")
    assert name == "opt[35]"
    name, _info = _resolve_field_by_canonical(_FULL_CARS_SCHEMA, "price_min")
    assert name == "topt[8][min]"
    name, info = _resolve_field_by_canonical({}, "brand")
    assert name == "opt[14]"  # synthetic path-based field
    assert info["type"] == "select"
    name, info = _resolve_field_by_canonical(_FULL_CARS_SCHEMA, "unknown_key")
    assert name is None


def test_options_kb_carries_canonical_key():
    options = [{"value": "1", "display_text": "Автомат"}]
    kb = filter_options_kb(1, fidx=0, options=options, page=0, lang="ru", ck="gearbox")
    packed = [
        b.callback_data
        for row in kb.inline_keyboard
        for b in row
        if b.callback_data and b.callback_data.startswith("fo:")
    ]
    assert packed
    cb = FilterOptCB.unpack(packed[0])
    assert cb.ck == "gearbox"


# ------------------------------------------------------------------ #
# C. Input-mode guards (handler-level interaction)                     #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_price_min_opens_numeric_prompt_not_options(ru_lang):
    callback = FakeCallback()
    state = FakeState(_cars_state_data())
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0, ck="price_min")
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    assert state.state == EditFilterFSM.waiting_value
    assert callback.message.edits
    text, markup = callback.message.edits[-1]
    assert "Изменение фильтра" in text
    assert "Цена от" in text
    assert "Пример: 5000" in text
    assert markup is not None
    # Cancel keyboard only: no option buttons
    all_cb = [b.callback_data or "" for row in markup.inline_keyboard for b in row]
    assert not any(cb.startswith("fo:") for cb in all_cb)
    assert not _RAW_KEY_RE.search(text)


@pytest.mark.asyncio
async def test_body_type_opens_body_options_not_gearbox(ru_lang):
    callback = FakeCallback()
    state = FakeState(_cars_state_data())
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0, ck="body_type")
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    assert state.state is None  # select mode never opens FSM text input
    text, markup = callback.message.edits[-1]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Универсал" in lbl for lbl in labels)
    assert not any("Автомат" in lbl for lbl in labels)
    opt_cbs = [
        FilterOptCB.unpack(b.callback_data)
        for row in markup.inline_keyboard
        for b in row
        if b.callback_data and b.callback_data.startswith("fo:")
    ]
    assert opt_cbs and all(cb.ck == "body_type" for cb in opt_cbs)


@pytest.mark.asyncio
async def test_gearbox_opens_gearbox_options(ru_lang):
    callback = FakeCallback()
    state = FakeState(_cars_state_data())
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0, ck="gearbox")
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    _text, markup = callback.message.edits[-1]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Автомат" in lbl for lbl in labels)
    assert not any("Универсал" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_invalid_canonical_key_is_rejected_localized(ru_lang):
    callback = FakeCallback()
    state = FakeState(_cars_state_data())
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0, ck="hack_key")
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    assert callback.answers
    text, show_alert = callback.answers[-1]
    assert show_alert is True
    assert text == get_text("filter_input_mode_error", "ru")
    assert not callback.message.edits


@pytest.mark.asyncio
async def test_model_without_brand_shows_localized_notice(ru_lang):
    callback = FakeCallback()
    state = FakeState(_cars_state_data())
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0, ck="model")
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    assert state.state is None
    text, _markup = callback.message.edits[-1]
    assert "Сначала выберите марку" in text
    assert not _RAW_KEY_RE.search(text)


def test_input_mode_resolution_from_registry():
    assert _input_mode_for("topt[8][min]", {"type": "text"}, "cars") == "numeric"
    assert _input_mode_for("topt[15][max]", {"type": "text"}, "cars") == "numeric"
    assert _input_mode_for("opt[32]", {"type": "select"}, "cars") == "select"
    assert _input_mode_for("opt[14]", {"type": "select"}, "cars") == "select"


# ------------------------------------------------------------------ #
# D. Brand provider: fallback list + non-brand exclusions              #
# ------------------------------------------------------------------ #


def test_fallback_brand_list_contains_known_brands():
    values = {o["value"] for o in _fallback_brand_slug_options()}
    assert {"bmw", "mercedes", "saab", "audi", "volkswagen", "volvo"}.issubset(values)


def test_brand_extraction_excludes_non_brand_sections():
    html = """
    <a href="/lv/transport/cars/bmw/">BMW</a>
    <a href="/lv/transport/cars/rare-cars/">Rare</a>
    <a href="/lv/transport/cars/exchange/">Exchange</a>
    <a href="/lv/transport/cars/spare-parts/">Parts</a>
    <a href="/lv/transport/cars/saab/">Saab</a>
    """
    values = {o["value"] for o in _extract_brand_slug_options_from_html(html, "lv")}
    assert {"bmw", "saab"}.issubset(values)
    assert not {"rare-cars", "exchange", "spare-parts"} & values


@pytest.mark.asyncio
async def test_brand_fetch_failure_uses_fallback(monkeypatch):
    class _BoomSession:
        def __init__(self, *a, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(filter_cmds.aiohttp, "ClientSession", _BoomSession)
    options = await filter_cmds._fetch_brand_slug_options(
        "https://www.ss.lv/lv/transport/cars/", "lv"
    )
    values = {o["value"] for o in options}
    assert {"bmw", "mercedes", "saab"}.issubset(values)


# ------------------------------------------------------------------ #
# E. Locale consistency (one language per screen)                      #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "lang,must_have,must_not_have",
    [
        ("ru", ["Цена от", "Год от", "Коробка передач", "Марка"], ["Cena no", "Gads no", "Price from", "Year from"]),
        ("lv", ["Cena no", "Gads no", "Pārnesumkārba", "Marka"], ["Цена от", "Год от", "Price from", "Gearbox"]),
        ("en", ["Price from", "Year from", "Gearbox", "Brand"], ["Цена от", "Cena no", "Gads no"]),
    ],
)
def test_fields_screen_single_locale(lang, must_have, must_not_have):
    fields = _sorted_fields(_FULL_CARS_SCHEMA, lang=lang, profile="cars")
    labels = [f[2] for f in fields]
    joined = " | ".join(labels)
    for token in must_have:
        assert token in joined, f"{token} missing for {lang}: {joined}"
    for token in must_not_have:
        assert token not in joined, f"{token} leaked into {lang}: {joined}"
    assert not _RAW_KEY_RE.search(joined)


# ------------------------------------------------------------------ #
# F. Dedup + stable composition across pages                           #
# ------------------------------------------------------------------ #


def test_canonical_keys_unique_and_stable_across_pages():
    fields = _sorted_fields(_FULL_CARS_SCHEMA, lang="ru", profile="cars")
    cks = [f[3] for f in fields]
    assert len(cks) == len(set(cks)), f"duplicate canonical keys: {cks}"
    assert cks == [
        "price_min", "price_max", "year_min", "year_max",
        "volume_min", "volume_max", "engine_type", "gearbox",
        "body_type", "color", "brand", "model",
    ]
    # Same input -> same order (stability)
    assert _sorted_fields(_FULL_CARS_SCHEMA, lang="ru", profile="cars") == fields
    # Collect ck across rendered pages: no repeats
    seen: list[str] = []
    for page in range(0, 2):
        kb = filter_fields_kb(search_id=1, fields=fields, page=page, lang="ru")
        for row in kb.inline_keyboard:
            for button in row:
                if button.callback_data and button.callback_data.startswith("fe:"):
                    cb = FilterEditCB.unpack(button.callback_data)
                    if cb.ck:
                        seen.append(cb.ck)
    assert len(seen) == len(set(seen))


# ------------------------------------------------------------------ #
# G. Prompt templates per canonical key                                #
# ------------------------------------------------------------------ #


def test_prompt_examples_match_key_domain_ru():
    year_prompt = _format_edit_prompt(
        lang="ru",
        field_name="topt[18][min]",
        field_info={"label": "", "type": "text", "options": []},
        current_value=None,
        profile="cars",
    )
    assert "Год от" in year_prompt and "Пример: 2018" in year_prompt
    assert "BMW" not in year_prompt

    volume_prompt = _format_edit_prompt(
        lang="ru",
        field_name="topt[15][max]",
        field_info={"label": "", "type": "text", "options": []},
        current_value=None,
        profile="cars",
    )
    assert "Объём до" in volume_prompt and "Пример: 2.0" in volume_prompt

    select_prompt = _format_edit_prompt(
        lang="ru",
        field_name="opt[35]",
        field_info={"label": "", "type": "select", "options": []},
        current_value="1",
        profile="cars",
    )
    assert "Коробка передач" in select_prompt
    assert "Выберите значение из списка ниже." in select_prompt
    assert "Пример: 5000" not in select_prompt


def test_prompt_examples_localized_lv_en():
    lv = _format_edit_prompt(
        lang="lv",
        field_name="topt[18][min]",
        field_info={"label": "", "type": "text", "options": []},
        current_value=None,
        profile="cars",
    )
    assert "Piemērs: 2018" in lv
    en = _format_edit_prompt(
        lang="en",
        field_name="topt[15][min]",
        field_info={"label": "", "type": "text", "options": []},
        current_value=None,
        profile="cars",
    )
    assert "Example: 2.0" in en


# ------------------------------------------------------------------ #
# H. Legacy saved filters render safely                                #
# ------------------------------------------------------------------ #


def test_legacy_unknown_raw_key_renders_generic_label():
    label_ru = filter_display_label("opt[999]", locale="ru", profile="cars")
    assert label_ru == "Параметр"
    label_lv = filter_display_label("topt[77][min]", locale="lv", profile="cars")
    assert label_lv == "Parametrs"
    assert not _RAW_KEY_RE.search(label_ru + label_lv)


@pytest.mark.asyncio
async def test_legacy_fidx_payload_still_resolves_for_cars(ru_lang):
    """Old buttons without ck must not crash: canonical derived from schema."""
    fields = _sorted_fields(_FULL_CARS_SCHEMA, lang="ru", profile="cars")
    assert fields  # sanity
    # simulate legacy: ck missing -> handler derives from field_order
    state = FakeState(_cars_state_data())
    callback = FakeCallback()
    cb_data = FilterEditCB(sid=1, fidx=0, pg=0)  # ck=None
    await cb_filter_edit_field(callback, cb_data, state, session_factory=None)
    # field_order[0] = topt[17][min] -> price_min -> numeric prompt
    assert state.state == EditFilterFSM.waiting_value
    text, _ = callback.message.edits[-1]
    assert "Цена от" in text


# ------------------------------------------------------------------ #
# I. Model as path slug (real SS.lv structure)                        #
# ------------------------------------------------------------------ #


def test_model_slug_extraction_from_brand_page():
    from app.bot.handlers.filter_cmds import _extract_model_slug_options_from_html
    html = """
    <a href="/lv/transport/cars/bmw/x5/">X5</a>
    <a href="/lv/transport/cars/bmw/320/">320</a>
    <a href="/lv/transport/cars/bmw/1-series/">1 Series</a>
    <a href="/lv/transport/cars/bmw/search/">Search</a>
    <a href="/msg/lv/transport/cars/bmw/x3/abcde.html">listing</a>
    """
    options = _extract_model_slug_options_from_html(html, "lv", "bmw")
    values = {o["value"] for o in options}
    assert {"x5", "320", "1-series", "x3"}.issubset(values)
    assert "search" not in values


def test_model_slug_url_rewrite():
    from app.bot.handlers.filter_cmds import _rewrite_cars_model_slug_in_url
    url = "https://www.ss.lv/lv/transport/cars/bmw/"
    assert "/transport/cars/bmw/x5/" in _rewrite_cars_model_slug_in_url(url, "x5")
    # No brand in path -> unchanged
    root = "https://www.ss.lv/lv/transport/cars/"
    assert _rewrite_cars_model_slug_in_url(root, "x5") == root


def test_brand_rewrite_truncates_stale_model_segment():
    from app.bot.handlers.filter_cmds import _rewrite_cars_brand_slug_in_url
    url = "https://www.ss.lv/lv/transport/cars/bmw/x5/"
    rewritten = _rewrite_cars_brand_slug_in_url(url, "audi")
    assert "/transport/cars/audi/" in rewritten
    assert "x5" not in rewritten
