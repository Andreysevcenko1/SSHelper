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
from app.services.filters import filters_from_json, filter_display_label
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


def _sorted_fields(schema: dict, lang: str = "lv") -> list[tuple[int, str, str]]:
    """Return (index, name, label) tuples sorted by name, labels resolved via filter_display_label."""
    items = []
    for i, (name, info) in enumerate(sorted(schema.items())):
        label = filter_display_label(name, schema, lang)
        items.append((i, name, label))
    return items


def _field_by_idx(schema: dict, fidx: int) -> tuple[str, dict] | tuple[None, None]:
    sorted_keys = sorted(schema.keys())
    if 0 <= fidx < len(sorted_keys):
        key = sorted_keys[fidx]
        return key, schema[key]
    return None, None


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
    return [f"  • {filter_display_label(k, schema, lang)} = {v}" for k, v in filters.items()]


def _autodetect_profile(search) -> str | None:
    """Auto-detect profile from a Search/GroupSearch URL for backward compatibility.

    For existing records that were saved before the ``category_profile`` column
    was introduced, we derive the profile on-the-fly from the stored URL.
    """
    from app.filters.profiles import detect_profile
    url = search.url or ""
    return detect_profile(url)


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
    finally:
        session.close()

    await message.answer(
        f"✅ <b>{filter_display_label(field)}</b> = <b>{value}</b> → #{sid}",
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
        await message.answer(
            get_text("err_filter_key_not_found", lang, key=field),
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
            "\n".join(lines),
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
        await _safe_edit(callback, text, reply_markup=filter_items_kb(sid, filters, lang=lang))

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

    fields = _sorted_fields(schema, lang)
    await state.update_data(schema=schema, sid=sid)

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
    finally:
        session.close()

    if not deleted:
        await callback.answer(
            get_text("err_filter_key_not_found", lang, key=callback_data.key),
            show_alert=True,
        )
        return

    if filters:
        content = "\n".join(_filters_lines(filters, lang=lang))
        text = get_text("filters_header", lang, sid=sid, content=content)
        await _safe_edit(callback, text, reply_markup=filter_items_kb(sid, filters, lang=lang))
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
        finally:
            session.close()
        schema = await _get_schema(search_url)
        await state.update_data(schema=schema, sid=sid)

    field_name, field_info = _field_by_idx(schema, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    label = (field_info.get("label") or field_name).strip()
    options = field_info.get("options", [])
    # Filter out blank/empty options
    options = [o for o in options if str(o.get("value", "")).strip()]

    if options:
        await _safe_edit(
            callback,
            get_text("filter_enter_value", lang, field=label),
            reply_markup=filter_options_kb(sid, callback_data.fidx, options, page=0, lang=lang),
        )
        await state.update_data(options=options)
    else:
        # Free-text input
        await state.set_state(EditFilterFSM.waiting_value)
        await state.update_data(
            field_name=field_name,
            field_label=label,
            sid=sid,
            prompt_msg_id=callback.message.message_id,
        )
        await _safe_edit(
            callback,
            get_text("filter_enter_value", lang, field=label),
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
        finally:
            session.close()
        schema = await _get_schema(search_url)
        await state.update_data(schema=schema, sid=sid)

    field_name, field_info = _field_by_idx(schema, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    # Re-build options if not cached
    if not options:
        raw_opts = field_info.get("options", [])
        options = [o for o in raw_opts if str(o.get("value", "")).strip()]

    if callback_data.vidx < 0 or callback_data.vidx >= len(options):
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    chosen = options[callback_data.vidx]
    value = str(chosen.get("value", ""))
    label = (field_info.get("label") or field_name).strip()

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

    if not schema:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
        finally:
            session.close()
        schema = await _get_schema(search_url)
        await state.update_data(schema=schema, sid=sid)

    if callback_data.ctx == "fields":
        fields = _sorted_fields(schema, lang)
        await _safe_edit(
            callback,
            get_text("filters_header", lang, sid=sid, content=""),
            reply_markup=filter_fields_kb(sid, fields, page=pg, lang=lang),
        )
    elif callback_data.ctx == "opts":
        fidx = callback_data.fidx
        field_name, field_info = _field_by_idx(schema, fidx)
        if field_name is None:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        options = [
            o for o in field_info.get("options", [])
            if str(o.get("value", "")).strip()
        ]
        label = (field_info.get("label") or field_name).strip()
        await _safe_edit(
            callback,
            get_text("filter_enter_value", lang, field=label),
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
                    text=get_text("filter_enter_value", lang, field=field_label),
                    reply_markup=cancel_kb(sid, lang=lang),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(
            get_text("filter_enter_value", lang, field=field_label),
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
