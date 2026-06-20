import json
import logging
from urllib.parse import urlparse

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository
from app.services.filters import (
    base_url_without_query,
    build_effective_url,
    extract_filters_from_url,
    filters_to_json,
    normalize_filters,
)
from app.services.ss_parser import SSParser, detect_category

logger = logging.getLogger(__name__)
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


def _format_filters(filters: dict, schema: dict) -> list[str]:
    """Return a list of human-readable filter description strings."""
    lines = []
    for key, value in filters.items():
        label = key
        if key in schema:
            schema_label = schema[key].get("label", "").strip()
            if schema_label and schema_label != key:
                label = schema_label

        if isinstance(value, list):
            display_value = ", ".join(str(v) for v in value)
        else:
            # Try to resolve option label from schema
            display_value = str(value)
            if key in schema and schema[key].get("options"):
                for opt in schema[key]["options"]:
                    if str(opt.get("value", "")) == str(value):
                        opt_text = opt.get("text", "").strip()
                        if opt_text:
                            display_value = opt_text
                        break

        lines.append(f"  • {label}: {display_value}")
    return lines


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

    # --- filter extraction ---
    raw_filters = extract_filters_from_url(url)
    normalized = normalize_filters(raw_filters)
    b_url = base_url_without_query(url)
    eff_url = build_effective_url(b_url, normalized) if normalized else url
    filters_json_str = filters_to_json(normalized)

    # --- discover available filter schema (best-effort, for logging) ---
    schema: dict = {}
    try:
        parser = SSParser()
        schema = await parser.discover_available_filters(url)
    except Exception as exc:
        logger.warning("cmd_add: could not discover filters for %s — %s", b_url, exc)

    # --- save to DB ---
    category = detect_category(url)
    category_label = _CATEGORY_LABELS.get(category, category)

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.add_search(
            user_id=user_id,
            url=url,
            title=category,
            base_url=b_url,
            filters_json=filters_json_str,
            effective_url=eff_url,
        )
    finally:
        session.close()

    # --- build response ---
    lines = [
        f"✅ Поиск добавлен!",
        f"ID: <b>{search.id}</b>",
        f"Категория: {category_label}",
        f"🔗 {eff_url}",
    ]

    if normalized:
        filter_lines = _format_filters(normalized, schema)
        lines.append("\n🔍 <b>Активные фильтры:</b>")
        lines.extend(filter_lines)
    else:
        lines.append("(без дополнительных фильтров)")

    await message.answer("\n".join(lines))


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
        display_url = s.effective_url or s.url
        entry = f"#{s.id} — {category_label} [{status}]\n🔗 {display_url}"
        if s.filters_json:
            try:
                filters = json.loads(s.filters_json)
                if filters:
                    filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
                    entry += f"\n🔍 {filter_str}"
            except (json.JSONDecodeError, TypeError):
                pass
        lines.append(entry)

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
