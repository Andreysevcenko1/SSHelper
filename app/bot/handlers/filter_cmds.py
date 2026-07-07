"""
Filter-related handlers:
- Slash commands: /filters, /setfilter, /delfilter, /clearfilters
- Callback handlers: FilterCB, FilterDelCB, FilterEditCB, FilterOptCB, PageCB
- FSM: EditFilterFSM.waiting_value for free-text filter input
"""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import FilterCB, FilterDelCB, FilterEditCB, FilterOptCB, PageCB
from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.filters import (
    after_filter_kb,
    cancel_kb,
    filter_fields_kb,
    filter_items_kb,
    filter_options_kb,
    filters_menu_kb,
    no_filters_kb,
)
from app.bot.keyboards.searches import after_action_kb, error_kb
from app.bot.states import EditFilterFSM
from app.bot.utils import try_delete_message
from app.db.repo import SearchRepository
from app.i18n import get_text
from app.services.filters import (
    base_url_without_query,
    build_effective_url,
    canonical_filter_key_for_profile,
    filter_display_label,
    filter_value_label,
    filters_from_json,
    sanitize_personal_ui_text,
)
from app.services.ss_parser import SSParser
from app.filters.renderer import render_canonical_filters

logger = logging.getLogger(__name__)
router = Router()

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

_NUMERIC_KEYWORDS = ("min", "max", "price", "pr_", "year", "run", "area", "floor", "room")


def _is_numeric_field(name: str, field_type: str) -> bool:
    name_lower = name.lower()
    return field_type in {"number"} or any(kw in name_lower for kw in _NUMERIC_KEYWORDS)


async def _get_schema(url: str) -> dict:
    try:
        parser = SSParser()
        return await parser.discover_available_filters(url)
    except Exception as exc:
        logger.warning("filter_cmds: could not fetch schema for %s — %s", url, exc)
        return {}


def _sorted_fields(schema: dict, lang: str = "lv", profile: str | None = None) -> list[tuple[int, str, str]]:
    """Return (index, name, label) tuples sorted by name, labels resolved via filter_display_label."""
    seen_canonical: set[str] = set()
    raw_items: list[tuple[str, dict, str]] = []
    for name, info in sorted(schema.items()):
        if str(info.get("type", "")).lower() == "hidden":
            continue
        canonical = canonical_filter_key_for_profile(name, profile) or name.lower()
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)
        label = filter_display_label(name, schema, lang, profile=profile)
        raw_items.append((name, info, label))

    items = []
    for i, (name, _info, label) in enumerate(raw_items):
        items.append((i, name, label))
    return items


def _field_by_idx(
    schema: dict,
    field_order: list[str],
    fidx: int,
) -> tuple[str, dict] | tuple[None, None]:
    if 0 <= fidx < len(field_order):
        key = field_order[fidx]
        if key in schema:
            return key, schema[key]
    return None, None


def _find_selected_brand(
    current_filters: dict[str, str | list[str]],
    profile: str | None,
) -> tuple[str, str] | None:
    for raw_key, raw_value in current_filters.items():
        canonical = canonical_filter_key_for_profile(raw_key, profile)
        if canonical == "brand":
            if isinstance(raw_value, list):
                if raw_value:
                    return raw_key, str(raw_value[0])
            else:
                return raw_key, str(raw_value)
    return None


def _is_mismatched_option_source(canonical_key: str, options: list[dict], locale: str) -> bool:
    known_fuel = {
        "Бензин", "Дизель", "Газ", "Гибрид", "Электро",
        "Benzīns", "Dīzelis", "Gāze", "Hibrīds", "Elektriskais",
        "Petrol", "Diesel", "Gas", "Hybrid", "Electric",
    }
    known_body = {
        "Седан", "Универсал", "Хэтчбек", "Купе", "Кабриолет", "Минивэн", "Внедорожник", "Пикап",
        "Sedans", "Universāls", "Hečbeks", "Kupe", "Kabriolets", "Minivens", "SUV/Džips", "Pikaps",
        "Sedan", "Estate", "Hatchback", "Coupe", "Convertible", "Minivan", "SUV", "Pickup",
    }
    texts = {str(opt.get("display_text") or opt.get("text") or "").strip() for opt in options}
    texts.discard("")
    if not texts:
        return False

    if canonical_key == "model":
        return len(texts & known_fuel) > 0 or len(texts & known_body) > 0
    if canonical_key == "brand":
        return len(texts & known_fuel) > 0
    if canonical_key == "fuel_type":
        return not bool(texts & known_fuel)
    if canonical_key == "body_type":
        return not bool(texts & known_body)
    return False


def _prepare_options_for_ui(
    *,
    field_name: str,
    options: list[dict],
    profile: str | None,
    lang: str,
    schema: dict | None = None,
) -> list[dict]:
    canonical = canonical_filter_key_for_profile(field_name, profile) or field_name
    prepared: list[dict] = []
    for opt in options:
        value = str(opt.get("value", "")).strip()
        if not value:
            continue
        display_text = filter_value_label(field_name, value, locale=lang, profile=profile, schema=schema)
        if display_text == value and not str(opt.get("text", "")).strip() and canonical in {
            "brand", "model", "fuel_type", "body_type", "gearbox", "color", "city_district",
        }:
            display_text = get_text("filter_option_unavailable", lang)
        if display_text == value and str(opt.get("text", "")).strip():
            display_text = str(opt.get("text", "")).strip()
        prepared.append({**opt, "display_text": sanitize_personal_ui_text(display_text, locale=lang, profile=profile)})

    logger.debug(
        "filter_options: canonical_key=%s locale=%s option_source=%s option_count=%d",
        canonical,
        lang,
        "schema",
        len(prepared),
    )
    return prepared


def _filters_lines(
    filters: dict,
    schema: dict | None = None,
    lang: str = "lv",
    profile: str | None = None,
) -> list[str]:
    """Format filters as bullet lines.

    Uses the profile-aware renderer when *profile* is given; falls back to
    the legacy ``filter_display_label``-based formatter otherwise.
    """
    if profile:
        return render_canonical_filters(filters, profile, locale=lang)
    return [
        f"  • {filter_display_label(k, schema, lang, profile=profile)} = "
        f"{filter_value_label(k, v, locale=lang, profile=profile, schema=schema)}"
        for k, v in filters.items()
    ]


def _autodetect_profile(search) -> str | None:
    """Auto-detect profile from a Search/GroupSearch URL for backward compatibility.

    For existing records that were saved before the ``category_profile`` column
    was introduced, we derive the profile on-the-fly from the stored URL.
    """
    from app.filters.profiles import detect_profile
    url = search.url or ""
    return detect_profile(url)


def _format_edit_prompt(
    *,
    lang: str,
    field_name: str,
    field_info: dict,
    current_value: str | None,
    profile: str | None,
) -> str:
    label = filter_display_label(field_name, schema={field_name: field_info}, locale=lang, profile=profile)
    current = (
        filter_value_label(
            field_name,
            current_value,
            locale=lang,
            profile=profile,
            schema={field_name: field_info},
        )
        if current_value
        else get_text("filter_current_value_missing", lang)
    )
    hint_key = "filter_hint_numeric" if _is_numeric_field(field_name, str(field_info.get("type", ""))) else "filter_hint_text"
    hint = get_text(hint_key, lang)
    prompt = get_text("filter_edit_prompt", lang, field=label, current=current, hint=hint)
    return sanitize_personal_ui_text(prompt, locale=lang, profile=profile)


async def _resolve_field_options(
    *,
    field_name: str,
    field_info: dict,
    search_url: str,
    current_filters: dict[str, str | list[str]],
    profile: str | None,
    lang: str,
    schema: dict,
) -> tuple[list[dict], str | None, str]:
    """Resolve options for a field with model-by-brand cascade and source guards."""
    canonical = canonical_filter_key_for_profile(field_name, profile) or field_name
    source = "schema"
    options = [
        o for o in field_info.get("options", [])
        if str(o.get("value", "")).strip()
    ]

    if canonical == "model":
        selected_brand = _find_selected_brand(current_filters, profile)
        if selected_brand is None:
            return [], get_text("filter_select_brand_first", lang), "missing_brand"
        brand_key, brand_value = selected_brand
        scoped_filters = dict(current_filters)
        scoped_filters[brand_key] = brand_value
        scoped_url = build_effective_url(base_url_without_query(search_url), scoped_filters)
        scoped_schema = await _get_schema(scoped_url)
        scoped_field = scoped_schema.get(field_name)
        if scoped_field is not None:
            options = [
                o for o in scoped_field.get("options", [])
                if str(o.get("value", "")).strip()
            ]
            source = "model_scoped_by_brand"
        else:
            return [], get_text("filter_options_unavailable", lang), "model_scoped_missing"

    prepared = _prepare_options_for_ui(
        field_name=field_name,
        options=options,
        profile=profile,
        lang=lang,
        schema=schema,
    )

    if _is_mismatched_option_source(canonical, prepared, lang):
        logger.error(
            "filter_option_source_guard: canonical_key=%s locale=%s option_source=%s option_count=%d",
            canonical,
            lang,
            source,
            len(prepared),
        )
        return [], get_text("filter_options_unavailable", lang), f"guard_mismatch:{canonical}"

    logger.debug(
        "filter_options_resolved: canonical_key=%s locale=%s option_source=%s option_count=%d",
        canonical,
        lang,
        source,
        len(prepared),
    )
    return prepared, None, source


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("_safe_edit failed: %s", exc)


# ------------------------------------------------------------------ #
# /filters <search_id>                                                 #
# ------------------------------------------------------------------ #


@router.message(Command("filters"))
async def cmd_filters(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            get_text("err_usage_filters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(
            get_text("err_usage_filters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    content = (
        "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        if filters
        else get_text("filters_none", lang)
    )
    text = get_text("filters_header", lang, sid=sid, content=content)
    await message.answer(text, reply_markup=filters_menu_kb(sid, bool(filters), lang=lang))


# ------------------------------------------------------------------ #
# /setfilter <search_id> <field> <value>                              #
# ------------------------------------------------------------------ #


@router.message(Command("setfilter"))
async def cmd_setfilter(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            get_text("err_usage_setfilter", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_setfilter", lang), reply_markup=error_kb(lang=lang))
        return

    field = parts[2].strip()
    value = parts[3].strip()

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        repo.set_filter(search, field, value)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    safe_label = filter_display_label(field, locale=lang, profile=profile)
    safe_value = filter_value_label(field, value, locale=lang, profile=profile)
    await message.answer(
        sanitize_personal_ui_text(
            f"✅ <b>{safe_label}</b> = <b>{safe_value}</b> → #{sid}",
            locale=lang,
            profile=profile,
        ),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# /delfilter <search_id> <field>                                       #
# ------------------------------------------------------------------ #


@router.message(Command("delfilter"))
async def cmd_delfilter(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            get_text("err_usage_delfilter", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_delfilter", lang), reply_markup=error_kb(lang=lang))
        return

    field = parts[2].strip()

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        deleted = repo.delete_filter(search, field)
        sid = search.id
    finally:
        session.close()

    if not deleted:
        safe_label = filter_display_label(field, locale=lang)
        await message.answer(
            get_text("err_filter_key_not_found", lang, key=safe_label),
            reply_markup=error_kb(back_search_id=sid, lang=lang),
        )
        return

    await message.answer(
        get_text("filter_deleted_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# /clearfilters <search_id>                                            #
# ------------------------------------------------------------------ #


@router.message(Command("clearfilters"))
async def cmd_clearfilters(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            get_text("err_usage_clearfilters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_clearfilters", lang), reply_markup=error_kb(lang=lang))
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        existing_filters = filters_from_json(search.filters_json)
        sid = search.id
        if not existing_filters:
            await message.answer(
                get_text("err_no_filters_set", lang),
                reply_markup=no_filters_kb(sid, lang=lang),
            )
            return
        repo.clear_filters(search)
    finally:
        session.close()

    await message.answer(
        get_text("filter_cleared_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# FilterCB: show / del_start / edit_start / clear                      #
# ------------------------------------------------------------------ #


@router.callback_query(FilterCB.filter(F.action == "show"))
async def cb_filter_show(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not filters:
        await _safe_edit(
            callback,
            get_text("err_no_filters_set", lang),
            reply_markup=no_filters_kb(sid, lang=lang),
        )
    else:
        lines = [get_text("filters_header", lang, sid=sid, content="")]
        lines += _filters_lines(filters, lang=lang, profile=profile)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text("\n".join(lines), locale=lang, profile=profile),
            reply_markup=filters_menu_kb(sid, bool(filters), lang=lang),
        )

    await callback.answer()


@router.callback_query(FilterCB.filter(F.action == "del_start"))
async def cb_filter_del_start(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    """Show filters with individual delete buttons."""
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not filters:
        await _safe_edit(
            callback,
            get_text("err_no_filters_set", lang),
            reply_markup=no_filters_kb(sid, lang=lang),
        )
    else:
        content = "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        text = get_text("filters_header", lang, sid=sid, content=content)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text(text, locale=lang),
            reply_markup=filter_items_kb(sid, filters, lang=lang, profile=profile),
        )

    await callback.answer()


@router.callback_query(FilterCB.filter(F.action == "edit_start"))
async def cb_filter_edit_start(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        search_url = search.effective_url or search.url
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
        current_filters = filters_from_json(search.filters_json)
    finally:
        session.close()

    await callback.answer("⏳")

    schema = await _get_schema(search_url)
    if not schema:
        await _safe_edit(
            callback,
            get_text("err_filter_schema", lang),
            reply_markup=error_kb(back_search_id=sid, lang=lang),
        )
        return

    fields = _sorted_fields(schema, lang, profile=profile)
    field_order = [name for _, name, _label in fields]
    await state.update_data(
        schema=schema,
        sid=sid,
        profile=profile,
        current_filters=current_filters,
        search_url=search_url,
        field_order=field_order,
    )

    await _safe_edit(
        callback,
        get_text("filters_header", lang, sid=sid, content=""),
        reply_markup=filter_fields_kb(sid, fields, page=0, lang=lang),
    )


@router.callback_query(FilterCB.filter(F.action == "clear"))
async def cb_filter_clear(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        existing_filters = filters_from_json(search.filters_json)
        sid = search.id
        if not existing_filters:
            await _safe_edit(
                callback,
                get_text("err_no_filters_set", lang),
                reply_markup=no_filters_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        repo.clear_filters(search)
    finally:
        session.close()

    await _safe_edit(
        callback,
        get_text("filter_cleared_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )
    await callback.answer()


# ------------------------------------------------------------------ #
# FilterDelCB: delete a single filter                                  #
# ------------------------------------------------------------------ #


@router.callback_query(FilterDelCB.filter())
async def cb_filter_delete_key(
    callback: CallbackQuery,
    callback_data: FilterDelCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        deleted = repo.delete_filter(search, callback_data.key)
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not deleted:
        safe_label = filter_display_label(callback_data.key, locale=lang, profile=profile)
        await callback.answer(
            get_text("err_filter_key_not_found", lang, key=safe_label),
            show_alert=True,
        )
        return

    if filters:
        content = "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        text = get_text("filters_header", lang, sid=sid, content=content)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text(text, locale=lang, profile=profile),
            reply_markup=filter_items_kb(sid, filters, lang=lang, profile=profile),
        )
    else:
        await _safe_edit(
            callback,
            get_text("filter_deleted_ok", lang),
            reply_markup=after_filter_kb(sid, lang=lang),
        )
    await callback.answer()


# ------------------------------------------------------------------ #
# FilterEditCB: field selected → show options or ask for text         #
# ------------------------------------------------------------------ #


@router.callback_query(FilterEditCB.filter())
async def cb_filter_edit_field(
    callback: CallbackQuery,
    callback_data: FilterEditCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    data = await state.get_data()
    schema: dict = data.get("schema", {})
    sid: int = data.get("sid", callback_data.sid)
    profile: str | None = data.get("profile")
    current_filters: dict = data.get("current_filters", {})
    search_url: str = data.get("search_url", "")
    field_order: list[str] = data.get("field_order", [])

    # Re-fetch schema if not in state (e.g. after restart)
    if not schema:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(callback_data.sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            sid = search.id
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [name for _, name, _label in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            current_filters=current_filters,
            search_url=search_url,
            field_order=field_order,
        )
    elif not search_url:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search:
                search_url = search.effective_url or search.url
                await state.update_data(search_url=search_url)
        finally:
            session.close()

    field_name, field_info = _field_by_idx(schema, field_order, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    options, unavailable_message, option_source = await _resolve_field_options(
        field_name=field_name,
        field_info=field_info,
        search_url=search_url,
        current_filters=current_filters,
        profile=profile,
        lang=lang,
        schema=schema,
    )

    if options:
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=current_filters.get(field_name),
                profile=profile,
            ),
            reply_markup=filter_options_kb(sid, callback_data.fidx, options, page=0, lang=lang),
        )
        await state.update_data(
            options=options,
            option_source=option_source,
            option_field_name=field_name,
            option_fidx=callback_data.fidx,
        )
    else:
        if unavailable_message:
            await _safe_edit(
                callback,
                sanitize_personal_ui_text(unavailable_message, locale=lang, profile=profile),
                reply_markup=after_filter_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        # Free-text input
        await state.set_state(EditFilterFSM.waiting_value)
        await state.update_data(
            field_name=field_name,
            field_label=filter_display_label(field_name, schema=schema, locale=lang, profile=profile),
            field_info=field_info,
            profile=profile,
            sid=sid,
            prompt_msg_id=callback.message.message_id,
        )
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=current_filters.get(field_name),
                profile=profile,
            ),
            reply_markup=cancel_kb(sid, lang=lang),
        )

    await callback.answer()


# ------------------------------------------------------------------ #
# FilterOptCB: option selected → save                                  #
# ------------------------------------------------------------------ #


@router.callback_query(FilterOptCB.filter())
async def cb_filter_opt(
    callback: CallbackQuery,
    callback_data: FilterOptCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    data = await state.get_data()
    schema: dict = data.get("schema", {})
    options: list = data.get("options", [])
    sid = callback_data.sid
    profile: str | None = data.get("profile")
    field_order: list[str] = data.get("field_order", [])
    option_field_name: str | None = data.get("option_field_name")

    if not schema:
        # Recover schema
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [name for _, name, _label in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            field_order=field_order,
            current_filters=current_filters,
            search_url=search_url,
        )

    if option_field_name and option_field_name in schema:
        field_name = option_field_name
        field_info = schema[field_name]
    else:
        field_name, field_info = _field_by_idx(schema, field_order, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    # Re-build options if not cached
    if not options:
        options = _prepare_options_for_ui(
            field_name=field_name,
            options=field_info.get("options", []),
            profile=profile,
            lang=lang,
            schema=schema,
        )

    if callback_data.vidx < 0 or callback_data.vidx >= len(options):
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    chosen = options[callback_data.vidx]
    value = str(chosen.get("value", ""))
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        repo.set_filter(search, field_name, value)
    finally:
        session.close()

    await state.clear()
    await _safe_edit(
        callback,
        get_text("filter_set_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )
    await callback.answer()


# ------------------------------------------------------------------ #
# PageCB: pagination                                                   #
# ------------------------------------------------------------------ #


@router.callback_query(PageCB.filter())
async def cb_page(
    callback: CallbackQuery,
    callback_data: PageCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    sid = callback_data.sid
    pg = callback_data.pg
    data = await state.get_data()
    schema: dict = data.get("schema", {})
    profile: str | None = data.get("profile")
    field_order: list[str] = data.get("field_order", [])
    current_filters: dict = data.get("current_filters", {})
    search_url: str = data.get("search_url", "")

    if not schema:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [name for _, name, _label in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            current_filters=current_filters,
            search_url=search_url,
            field_order=field_order,
        )
    elif not search_url:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search:
                search_url = search.effective_url or search.url
                await state.update_data(search_url=search_url)
        finally:
            session.close()

    if callback_data.ctx == "fields":
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [name for _, name, _label in fields]
        await state.update_data(field_order=field_order)
        await _safe_edit(
            callback,
            get_text("filters_header", lang, sid=sid, content=""),
            reply_markup=filter_fields_kb(sid, fields, page=pg, lang=lang),
        )
    elif callback_data.ctx == "opts":
        fidx = callback_data.fidx
        field_name, field_info = _field_by_idx(schema, field_order, fidx)
        if field_name is None:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        options, unavailable_message, option_source = await _resolve_field_options(
            field_name=field_name,
            field_info=field_info,
            search_url=search_url,
            current_filters=current_filters,
            profile=profile,
            lang=lang,
            schema=schema,
        )
        if unavailable_message:
            await _safe_edit(
                callback,
                sanitize_personal_ui_text(unavailable_message, locale=lang, profile=profile),
                reply_markup=after_filter_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        await state.update_data(
            options=options,
            option_source=option_source,
            option_field_name=field_name,
            option_fidx=fidx,
        )
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=(data.get("current_filters") or {}).get(field_name),
                profile=profile,
            ),
            reply_markup=filter_options_kb(sid, fidx, options, page=pg, lang=lang),
        )

    await callback.answer()


# ------------------------------------------------------------------ #
# EditFilterFSM.waiting_value: receive free-text value                 #
# ------------------------------------------------------------------ #


@router.message(EditFilterFSM.waiting_value, F.text)
async def fsm_filter_value(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)

    data = await state.get_data()
    field_name: str = data.get("field_name", "")
    field_label: str = data.get("field_label", field_name)
    field_info: dict = data.get("field_info", {"name": field_name, "type": "text"})
    profile: str | None = data.get("profile")
    sid: int = data.get("sid", 0)
    prompt_msg_id: int | None = data.get("prompt_msg_id")
    value = (message.text or "").strip()

    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    if not value:
        # Re-prompt
        if prompt_msg_id and message.bot:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=_format_edit_prompt(
                        lang=lang,
                        field_name=field_name,
                        field_info=field_info,
                        current_value=None,
                        profile=profile,
                    ),
                    reply_markup=cancel_kb(sid, lang=lang),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=None,
                profile=profile,
            ),
            reply_markup=cancel_kb(sid, lang=lang),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(sid)
        if search is None or search.user_id != user_id:
            await state.clear()
            await message.answer(
                get_text("err_search_not_found_short", lang),
                reply_markup=error_kb(lang=lang),
            )
            return
        repo.set_filter(search, field_name, value)
    finally:
        session.close()

    await state.clear()

    text = get_text("filter_set_ok", lang)
    kb = after_filter_kb(sid, lang=lang)

    if prompt_msg_id and message.bot:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                reply_markup=kb,
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)
