import json
import logging
from urllib.parse import urlparse

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.keyboards.searches import (
    after_action_kb,
    error_kb,
    searches_list_kb,
)
from app.db.repo import SearchRepository
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
        await message.answer("Не удалось определить пользователя.")
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        searches = repo.get_user_searches(user_id)
    finally:
        session.close()

    if not searches:
        await message.answer(
            "📋 У вас нет поисков.\n\nДобавьте первый поиск, нажав кнопку ниже.",
            reply_markup=searches_list_kb([]),
        )
        return

    lines = [f"📋 <b>Ваши поиски</b> ({len(searches)}):\n"]
    for s in searches:
        from app.bot.keyboards.searches import CATEGORY_LABELS
        status = "▶️ активен" if s.is_active else "⏸ на паузе"
        category_label = CATEGORY_LABELS.get(s.title, s.title)
        display_url = s.effective_url or s.url
        entry = f"#{s.id} — {category_label} [{status}]\n🔗 {display_url}"
        filters = filters_from_json(s.filters_json)
        if filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            entry += f"\n🔍 {filter_str}"
        lines.append(entry)

    await message.answer("\n\n".join(lines), reply_markup=searches_list_kb(searches))


@router.message(Command("pause"))
async def cmd_pause(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            "Использование: /pause <ID поиска>",
            reply_markup=error_kb(),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.", reply_markup=error_kb())
            return
        if not search.is_active:
            await message.answer(
                f"Поиск #{search_id} уже на паузе.",
                reply_markup=error_kb(back_search_id=search_id),
            )
            return
        repo.pause_search(search)
    finally:
        session.close()

    await message.answer(
        f"⏸ Поиск #{search_id} поставлен на паузу.",
        reply_markup=after_action_kb(),
    )


@router.message(Command("resume"))
async def cmd_resume(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            "Использование: /resume <ID поиска>",
            reply_markup=error_kb(),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.", reply_markup=error_kb())
            return
        if search.is_active:
            await message.answer(
                f"Поиск #{search_id} уже активен.",
                reply_markup=error_kb(back_search_id=search_id),
            )
            return
        repo.resume_search(search)
    finally:
        session.close()

    await message.answer(
        f"▶️ Поиск #{search_id} возобновлён.",
        reply_markup=after_action_kb(),
    )


@router.message(Command("delete"))
async def cmd_delete(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer(
            "Использование: /delete <ID поиска>",
            reply_markup=error_kb(),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.", reply_markup=error_kb())
            return
        repo.delete_search(search)
    finally:
        session.close()

    await message.answer(
        f"🗑 Поиск #{search_id} удалён.",
        reply_markup=after_action_kb(),
    )


def _parse_search_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None

