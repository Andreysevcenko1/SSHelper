"""Callback handlers for main navigation: MenuCB and SearchCB."""
import json
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import MenuCB, SearchCB
from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.searches import (
    CATEGORY_LABELS,
    after_action_kb,
    error_kb,
    search_actions_kb,
    searches_list_kb,
)
from app.bot.keyboards.filters import filters_menu_kb
from app.bot.states import AddSearchFSM
from app.db.repo import SearchRepository
from app.services.filters import filters_from_json

logger = logging.getLogger(__name__)
router = Router()

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

WELCOME_TEXT = (
    "👋 <b>SSHelper</b> — мониторинг объявлений SS.lv\n\n"
    "Выберите действие:"
)


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """Edit the callback message, ignoring 'message not modified' errors."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _format_search_details(search, filters: dict, schema: dict | None = None) -> str:
    category_label = CATEGORY_LABELS.get(search.title, search.title)
    status = "▶️ активен" if search.is_active else "⏸ на паузе"
    display_url = search.effective_url or search.url
    lines = [
        f"🔎 <b>Поиск #{search.id}</b>",
        f"Категория: {category_label}",
        f"Статус: {status}",
        f"🔗 {display_url}",
    ]
    if filters:
        lines.append("\n🔍 <b>Активные фильтры:</b>")
        for k, v in filters.items():
            lines.append(f"  • {k}: {v}")
    else:
        lines.append("\n(без дополнительных фильтров)")
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# MenuCB handlers                                                      #
# ------------------------------------------------------------------ #


@router.callback_query(MenuCB.filter(F.action == "main"))
async def cb_menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _safe_edit(callback, WELCOME_TEXT, reply_markup=main_menu_kb())
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
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        searches = repo.get_user_searches(user_id)
    finally:
        session.close()

    if not searches:
        text = "📋 У вас нет поисков.\n\nДобавьте первый поиск, нажав кнопку ниже."
        kb = searches_list_kb([])
    else:
        text = f"📋 <b>Ваши поиски</b> ({len(searches)}):\n\nВыберите поиск для просмотра или управления:"
        kb = searches_list_kb(searches)

    await _safe_edit(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "add_start"))
async def cb_menu_add_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    from app.bot.keyboards.filters import cancel_kb

    await state.clear()
    await state.set_state(AddSearchFSM.waiting_url)
    await state.update_data(prompt_msg_id=callback.message.message_id)

    await _safe_edit(
        callback,
        "➕ <b>Добавить поиск</b>\n\n"
        "Отправьте ссылку на страницу поиска SS.lv.\n\n"
        "<i>Пример:</i>\n"
        "<code>https://www.ss.lv/lv/transport/cars/</code>",
        reply_markup=cancel_kb(),
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
        await callback.answer("Нет пользователя.", show_alert=True)
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await _safe_edit(
                callback,
                "❌ Поиск не найден или не принадлежит вам.",
                reply_markup=error_kb(),
            )
            await callback.answer()
            return
        filters = filters_from_json(search.filters_json)
        text = _format_search_details(search, filters)
        kb = search_actions_kb(search.id, search.is_active)
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
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer("❌ Поиск не найден.", show_alert=True)
            return
        if not search.is_active:
            await callback.answer("⏸ Поиск уже на паузе.", show_alert=True)
            return
        repo.pause_search(search)
        sid = search.id
    finally:
        session.close()

    await _safe_edit(
        callback,
        f"⏸ Поиск #{sid} поставлен на паузу.",
        reply_markup=after_action_kb(),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "resume"))
async def cb_search_resume(
    callback: CallbackQuery,
    callback_data: SearchCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer("❌ Поиск не найден.", show_alert=True)
            return
        if search.is_active:
            await callback.answer("▶️ Поиск уже активен.", show_alert=True)
            return
        repo.resume_search(search)
        sid = search.id
    finally:
        session.close()

    await _safe_edit(
        callback,
        f"▶️ Поиск #{sid} возобновлён.",
        reply_markup=after_action_kb(),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "delete"))
async def cb_search_delete(
    callback: CallbackQuery,
    callback_data: SearchCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer("❌ Поиск не найден.", show_alert=True)
            return
        sid = search.id
        repo.delete_search(search)
    finally:
        session.close()

    await _safe_edit(
        callback,
        f"🗑 Поиск #{sid} удалён.",
        reply_markup=after_action_kb(),
    )
    await callback.answer()


@router.callback_query(SearchCB.filter(F.action == "filters"))
async def cb_search_filters(
    callback: CallbackQuery,
    callback_data: SearchCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer("❌ Поиск не найден.", show_alert=True)
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
    finally:
        session.close()

    text = (
        f"🔍 <b>Фильтры поиска #{sid}</b>\n\n"
        + (
            "\n".join(f"  • {k}: {v}" for k, v in filters.items())
            if filters
            else "(фильтры не установлены)"
        )
    )
    await _safe_edit(
        callback,
        text,
        reply_markup=filters_menu_kb(sid, bool(filters)),
    )
    await callback.answer()
