from urllib.parse import urlparse

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message, session_factory: sessionmaker[Session]) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    command_parts = (message.text or "").split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("Использование: /add <ссылка_на_поиск_ss.lv>")
        return

    url = command_parts[1].strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or "ss.lv" not in (parsed.netloc or ""):
        await message.answer("Нужна валидная ссылка на ss.lv")
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.add_search(user_id=message.from_user.id, url=url, title="SS.lv search")
    finally:
        session.close()

    await message.answer(f"Поиск добавлен. ID: {search.id}")
