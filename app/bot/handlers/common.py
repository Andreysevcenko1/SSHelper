import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.keyboards.main import main_menu_kb
from app.bot.utils import try_delete_message
from app.db.repo import ReferralRepository, TrialRepository, UserSettingsRepository
from app.i18n import get_text, resolve_lang

logger = logging.getLogger(__name__)

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
async def cmd_start(
    message: Message,
    command: CommandObject,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    # Start the free-trial clock at first contact.
    if user_id:
        session = session_factory()
        try:
            TrialRepository(session).get_or_start(user_id)
        finally:
            session.close()

    # Referral deep link: /start ref_<referrer_id>
    args = (command.args or "").strip()
    if user_id and args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
        except ValueError:
            referrer_id = 0
        if referrer_id:
            session = session_factory()
            try:
                credited = ReferralRepository(session).credit(referrer_id, user_id)
            finally:
                session.close()
            if credited:
                ref_lang = get_user_lang(referrer_id, None, session_factory)
                try:
                    await message.bot.send_message(
                        referrer_id, get_text("ref_credited", ref_lang)
                    )
                except Exception:
                    logger.debug("Could not notify referrer %s", referrer_id)

    sent = await message.answer(get_text("welcome", lang), reply_markup=main_menu_kb(lang=lang))
    # Pin the menu so it stays reachable when notifications push it up.
    try:
        await sent.bot.unpin_all_chat_messages(chat_id=sent.chat.id)
    except Exception:
        pass
    try:
        await sent.bot.pin_chat_message(
            chat_id=sent.chat.id,
            message_id=sent.message_id,
            disable_notification=True,
        )
    except Exception:
        logger.debug("Could not pin menu message in chat %s", sent.chat.id, exc_info=True)

