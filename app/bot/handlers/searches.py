from urllib.parse import urlparse

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository
from app.services.ss_parser import detect_category

router = Router()

_CATEGORY_LABELS = {
    "Транспорт": "🚗 Транспорт",
    "Недвижимость": "🏠 Недвижимость",
    "Животные": "🐾 Животные",
    "Электроника": "💻 Электроника",
    "Услуги": "🔧 Услуги",
    "Прочее": "📦 Прочее",
    "Одежда": "👗 Одежда",
    "Сад и огород": "🌱 Сад и огород",
    "Еда": "🍎 Еда",
    "Спорт": "⚽ Спорт",
    "Бизнес": "💼 Бизнес",
    "Коллекционирование": "🏺 Коллекционирование",
    "Дом и быт": "🏡 Дом и быт",
    "SS.lv": "📋 SS.lv",
}


def _validate_ss_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and "ss.lv" in (parsed.netloc or "")


def _require_user(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id


@router.message(Command("add"))
async def cmd_add(message: Message, session_factory: sessionmaker[Session]) -> None:
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    command_parts = (message.text or "").split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("Использование: /add <ссылка_на_поиск_ss.lv>")
        return

    url = command_parts[1].strip()
    if not _validate_ss_url(url):
        await message.answer("❌ Нужна валидная ссылка на ss.lv (например: https://www.ss.lv/lv/transport/cars/)")
        return

    category = detect_category(url)
    category_label = _CATEGORY_LABELS.get(category, category)

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.add_search(user_id=user_id, url=url, title=category)
    finally:
        session.close()

    await message.answer(
        f"✅ Поиск добавлен!\n"
        f"ID: <b>{search.id}</b>\n"
        f"Категория: {category_label}\n"
        f"🔗 {url}"
    )


@router.message(Command("list"))
async def cmd_list(message: Message, session_factory: sessionmaker[Session]) -> None:
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
        await message.answer("У вас нет активных поисков. Добавьте командой /add <ссылка>")
        return

    lines = ["📋 <b>Ваши поиски:</b>\n"]
    for s in searches:
        status = "▶️ активен" if s.is_active else "⏸ на паузе"
        category_label = _CATEGORY_LABELS.get(s.title, s.title)
        lines.append(f"#{s.id} — {category_label} [{status}]\n🔗 {s.url}")

    await message.answer("\n".join(lines))


@router.message(Command("pause"))
async def cmd_pause(message: Message, session_factory: sessionmaker[Session]) -> None:
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer("Использование: /pause <ID поиска>")
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.")
            return
        if not search.is_active:
            await message.answer(f"Поиск #{search_id} уже на паузе.")
            return
        repo.pause_search(search)
    finally:
        session.close()

    await message.answer(f"⏸ Поиск #{search_id} поставлен на паузу.")


@router.message(Command("resume"))
async def cmd_resume(message: Message, session_factory: sessionmaker[Session]) -> None:
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer("Использование: /resume <ID поиска>")
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.")
            return
        if search.is_active:
            await message.answer(f"Поиск #{search_id} уже активен.")
            return
        repo.resume_search(search)
    finally:
        session.close()

    await message.answer(f"▶️ Поиск #{search_id} возобновлён.")


@router.message(Command("delete"))
async def cmd_delete(message: Message, session_factory: sessionmaker[Session]) -> None:
    user_id = _require_user(message)
    if user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    search_id = _parse_search_id(message)
    if search_id is None:
        await message.answer("Использование: /delete <ID поиска>")
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer("❌ Поиск не найден.")
            return
        repo.delete_search(search)
    finally:
        session.close()

    await message.answer(f"🗑 Поиск #{search_id} удалён.")


def _parse_search_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None
