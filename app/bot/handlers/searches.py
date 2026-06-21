import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.searches import (
    after_action_kb,
    error_kb,
    no_searches_kb,
    searches_list_kb,
)
from app.db.repo import SearchRepository
from app.i18n import get_text
from app.services.filters import filters_from_json
from app.bot.utils import try_delete_message

logger = logging.getLogger(__name__)
router = Router()


def _require_user(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id


@router.message(Command("list"))
async def cmd_list(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer(get_text("err_no_user", "lv"))
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    session = session_factory()
    try:
        repo = SearchRepository(session)
        searches = repo.get_user_searches(user_id)
    finally:
        session.close()

    if not searches:
        await message.answer(
            get_text("no_searches", lang),
            reply_markup=no_searches_kb(lang=lang),
        )
        return

    lines = [get_text("list_header", lang, count=len(searches))]
    for s in searches:
        from app.bot.keyboards.searches import CATEGORY_LABELS
        status = get_text("status_active" if s.is_active else "status_paused", lang)
        category_label = CATEGORY_LABELS.get(s.title, s.title)
        display_url = s.effective_url or s.url
        entry = f"#{s.id} — {category_label} [{status}]\n🔗 {display_url}"
        filters = filters_from_json(s.filters_json)
        if filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            entry += f"\n🔍 {filter_str}"
        lines.append(entry)

    await message.answer("\n\n".join(lines), reply_markup=searches_list_kb(searches, lang=lang))


@router.message(Command("pause"))
async def cmd_pause(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer(get_text("err_no_user", "lv"))
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            get_text("err_usage_pause", lang),
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
        if not search.is_active:
            await message.answer(
                get_text("err_search_already_exists_pause", lang, sid=search_id),
                reply_markup=error_kb(back_search_id=search_id, lang=lang),
            )
            return
        repo.pause_search(search)
    finally:
        session.close()

    await message.answer(
        get_text("search_paused", lang, sid=search_id),
        reply_markup=after_action_kb(search_id=search_id, lang=lang),
    )


@router.message(Command("resume"))
async def cmd_resume(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer(get_text("err_no_user", "lv"))
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            get_text("err_usage_resume", lang),
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
        if search.is_active:
            await message.answer(
                get_text("err_search_already_active_resume", lang, sid=search_id),
                reply_markup=error_kb(back_search_id=search_id, lang=lang),
            )
            return
        repo.resume_search(search)
    finally:
        session.close()

    await message.answer(
        get_text("search_resumed", lang, sid=search_id),
        reply_markup=after_action_kb(search_id=search_id, lang=lang),
    )


@router.message(Command("delete"))
async def cmd_delete(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer(get_text("err_no_user", "lv"))
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            get_text("err_usage_delete", lang),
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
        repo.delete_search(search)
    finally:
        session.close()

    await message.answer(
        get_text("search_deleted", lang, sid=search_id),
        reply_markup=after_action_kb(lang=lang),
    )


def _parse_search_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None

