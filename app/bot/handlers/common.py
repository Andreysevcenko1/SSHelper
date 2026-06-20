from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.keyboards.main import main_menu_kb
from app.bot.utils import try_delete_message
from app.db.repo import UserSettingsRepository
from app.i18n import get_text, resolve_lang

router = Router()


def get_user_lang(
    user_id: int,
    tg_lang: str | None,
    session_factory: sessionmaker[Session],
) -> str:
    """Resolve the effective language for a user from DB + Telegram fallback."""
    session = session_factory()
    try:
        db_lang = UserSettingsRepository(session).get_lang(user_id)
    finally:
        session.close()
    return resolve_lang(tg_lang, db_lang)


@router.message(Command("start"))
async def cmd_start(message: Message, session_factory: sessionmaker[Session]) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    await message.answer(get_text("welcome", lang), reply_markup=main_menu_kb(lang=lang))

