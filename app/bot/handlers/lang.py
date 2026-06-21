"""Handlers for language selection: /lang command and LangCB callbacks."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import LangCB, MenuCB
from app.bot.keyboards.main import lang_selection_kb, main_menu_kb
from app.bot.utils import try_delete_message
from app.db.repo import UserSettingsRepository
from app.i18n import get_text, resolve_lang

logger = logging.getLogger(__name__)
router = Router()


def _get_user_lang(
    user_id: int,
    tg_lang: str | None,
    session_factory: sessionmaker[Session],
) -> str:
    """Resolve effective language for the user."""
    session = session_factory()
    try:
        db_lang = UserSettingsRepository(session).get_lang(user_id)
    finally:
        session.close()
    return resolve_lang(tg_lang, db_lang)


@router.message(Command("lang"))
async def cmd_lang(
    message: Message,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = _get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    await message.answer(
        get_text("lang_select_prompt", lang),
        reply_markup=lang_selection_kb(lang=lang),
    )


@router.callback_query(MenuCB.filter(F.action == "lang"))
async def cb_menu_lang(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = _get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    try:
        await callback.message.edit_text(
            get_text("lang_select_prompt", lang),
            reply_markup=lang_selection_kb(lang=lang),
        )
    except Exception as exc:
        logger.debug("cb_menu_lang edit failed: %s", exc)
    await callback.answer()


@router.callback_query(LangCB.filter())
async def cb_lang_select(
    callback: CallbackQuery,
    callback_data: LangCB,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else None
    if user_id is None:
        await callback.answer("Error", show_alert=True)
        return

    new_lang = callback_data.lang
    session = session_factory()
    try:
        UserSettingsRepository(session).set_lang(user_id, new_lang)
    finally:
        session.close()

    confirmation = get_text("lang_changed", new_lang)
    try:
        await callback.message.edit_text(
            f"{confirmation}\n\n{get_text('menu_welcome', new_lang)}",
            reply_markup=main_menu_kb(lang=new_lang),
        )
    except Exception as exc:
        logger.debug("cb_lang_select edit failed: %s", exc)
    await callback.answer(confirmation)
