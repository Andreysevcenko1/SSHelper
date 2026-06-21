"""Callback handlers for main navigation: MenuCB and SearchCB."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import MenuCB, SearchCB
from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.searches import (
    after_action_kb,
    error_kb,
    no_searches_kb,
    search_actions_kb,
    searches_list_kb,
)
from app.bot.keyboards.filters import filters_menu_kb
from app.bot.states import AddSearchFSM
from app.db.repo import SearchRepository
from app.i18n import get_text, translate_category
from app.services.filters import filters_from_json

logger = logging.getLogger(__name__)
router = Router()


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """Edit the callback message, ignoring 'message not modified' errors."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("_safe_edit failed: %s", exc)


def _format_search_details(search, filters: dict, lang: str) -> str:
    category_label = translate_category(search.title, lang)
    status = get_text("status_active" if search.is_active else "status_paused", lang)
    display_url = search.effective_url or search.url
    lines = [
        get_text("search_detail_header", lang, sid=search.id),
        get_text("search_detail_category", lang, cat=category_label),
        get_text("search_detail_status", lang, status=status),
        f"🔗 {display_url}",
    ]
    if not search.is_active:
        lines.append(f"\n⚠️ {get_text('err_already_paused', lang)}")
    if filters:
        lines.append(get_text("search_detail_active_filters", lang))
        for k, v in filters.items():
            lines.append(f"  • {k}: {v}")
    else:
        lines.append(get_text("search_detail_no_filters", lang))
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# MenuCB handlers                                                      #
# ------------------------------------------------------------------ #


@router.callback_query(MenuCB.filter(F.action == "main"))
async def cb_menu_main(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    await _safe_edit(
        callback,
        get_text("menu_welcome", lang),
        reply_markup=main_menu_kb(lang=lang),
    )
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "help"))
async def cb_menu_help(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    await _safe_edit(
        callback,
        get_text("help_text", lang),
        reply_markup=main_menu_kb(lang=lang),
    )
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "searches"))
async def cb_menu_searches(
    callback: CallbackQuery,
    callback_data: MenuCB,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else None
    if user_id is None:
        await callback.answer(get_text("err_no_user", "lv"), show_alert=True)
        return

    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    session = session_factory()
    try:
        repo = SearchRepository(session)
        searches = repo.get_user_searches(user_id)
    finally:
        session.close()

    if not searches:
        text = get_text("no_searches", lang)
        kb = no_searches_kb(lang=lang)
    else:
        text = get_text("searches_list_header", lang, count=len(searches))
        kb = searches_list_kb(searches, lang=lang)

    await _safe_edit(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "add_start"))
async def cb_menu_add_start(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    from app.bot.keyboards.filters import cancel_kb

    await state.clear()
    await state.set_state(AddSearchFSM.waiting_url)
    await state.update_data(prompt_msg_id=callback.message.message_id)

    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    await _safe_edit(
        callback,
        get_text("add_search_prompt", lang),
        reply_markup=cancel_kb(lang=lang),
    )
    await callback.answer()


# ------------------------------------------------------------------ #
# SearchCB handlers                                                    #
# ------------------------------------------------------------------ #


@router.callback_query(SearchCB.filter(F.action == "view"))
async def cb_search_view(
    callback: CallbackQuery,
    callback_data: SearchCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    if user_id is None:
        await callback.answer(get_text("err_no_user", "lv"), show_alert=True)
        return

    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await _safe_edit(
                callback,
                get_text("err_search_not_found_id", lang, sid=callback_data.sid),
                reply_markup=error_kb(lang=lang),
            )
            await callback.answer()
            return
        filters = filters_from_json(search.filters_json)
        text = _format_search_details(search, filters, lang)
        kb = search_actions_kb(search.id, search.is_active, lang=lang)
    finally:
        session.close()

    await _safe_edit(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "pause"))
async def cb_search_pause(
    callback: CallbackQuery,
    callback_data: SearchCB,
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
            await callback.answer(
                get_text("err_search_not_found_short", lang), show_alert=True
            )
            return
        if not search.is_active:
            await callback.answer(get_text("err_already_paused", lang), show_alert=True)
            return
        repo.pause_search(search)
        sid = search.id
    finally:
        session.close()

    await _safe_edit(
        callback,
        get_text("search_paused", lang, sid=sid),
        reply_markup=after_action_kb(search_id=sid, lang=lang),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "resume"))
async def cb_search_resume(
    callback: CallbackQuery,
    callback_data: SearchCB,
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
            await callback.answer(
                get_text("err_search_not_found_short", lang), show_alert=True
            )
            return
        if search.is_active:
            await callback.answer(get_text("err_already_active", lang), show_alert=True)
            return
        repo.resume_search(search)
        sid = search.id
    finally:
        session.close()

    await _safe_edit(
        callback,
        get_text("search_resumed", lang, sid=sid),
        reply_markup=after_action_kb(search_id=sid, lang=lang),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "delete"))
async def cb_search_delete(
    callback: CallbackQuery,
    callback_data: SearchCB,
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
            await callback.answer(
                get_text("err_search_not_found_short", lang), show_alert=True
            )
            return
        sid = search.id
        repo.delete_search(search)
    finally:
        session.close()

    from app.bot.keyboards.searches import no_searches_kb
    from app.bot.keyboards.main import main_menu_kb as _main_kb

    await _safe_edit(
        callback,
        get_text("search_deleted", lang, sid=sid),
        reply_markup=after_action_kb(lang=lang),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "filters"))
async def cb_search_filters(
    callback: CallbackQuery,
    callback_data: SearchCB,
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
            await callback.answer(
                get_text("err_search_not_found_short", lang), show_alert=True
            )
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
    finally:
        session.close()

    content = (
        "\n".join(f"  • {k}: {v}" for k, v in filters.items())
        if filters
        else get_text("filters_none", lang)
    )
    text = get_text("filters_header", lang, sid=sid, content=content)
    await _safe_edit(
        callback,
        text,
        reply_markup=filters_menu_kb(sid, bool(filters), lang=lang),
    )
    await callback.answer()
