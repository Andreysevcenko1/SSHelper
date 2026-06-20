"""AddSearchFSM: multi-step flow for adding a new search via URL input."""
import logging
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.filters import cancel_kb
from app.bot.keyboards.searches import after_add_kb, CATEGORY_LABELS
from app.bot.states import AddSearchFSM
from app.bot.utils import try_delete_message
from app.db.repo import SearchRepository
from app.i18n import get_text
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


def _validate_ss_url(url: str) -> str | None:
    """Return None if valid, or a human-readable error string (language-agnostic)."""
    url = url.strip()
    if not url:
        return "empty"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "bad_scheme"
    if not parsed.netloc or "ss.lv" not in parsed.netloc:
        return "bad_domain"
    return None


def _format_filters(normalized: dict, schema: dict) -> list[str]:
    lines = []
    for key, value in normalized.items():
        label = key
        if key in schema:
            schema_label = schema[key].get("label", "").strip()
            if schema_label and schema_label != key:
                label = schema_label
        if isinstance(value, list):
            display_value = ", ".join(str(v) for v in value)
        else:
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


# ------------------------------------------------------------------ #
# /add command: inline (with URL) or start FSM (without URL)          #
# ------------------------------------------------------------------ #


@router.message(Command("add"), StateFilter(None))
async def cmd_add(
    message: Message,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    command_parts = (message.text or "").split(maxsplit=1)
    if len(command_parts) < 2:
        # No URL provided – start FSM
        prompt = await message.answer(
            get_text("add_search_prompt", lang),
            reply_markup=cancel_kb(lang=lang),
        )
        await state.set_state(AddSearchFSM.waiting_url)
        await state.update_data(prompt_msg_id=prompt.message_id)
        return

    url = command_parts[1].strip()
    await _process_add_url(message=message, url=url, session_factory=session_factory, lang=lang)


# ------------------------------------------------------------------ #
# FSM: waiting for URL text                                            #
# ------------------------------------------------------------------ #


@router.message(AddSearchFSM.waiting_url, F.text)
async def fsm_add_url(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    url = (message.text or "").strip()
    await try_delete_message(message)

    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    data = await state.get_data()
    prompt_msg_id: int | None = data.get("prompt_msg_id")

    error_code = _validate_ss_url(url)
    if error_code:
        error_msg = get_text("err_invalid_url", lang)
        # Edit the prompt to show the error and keep the cancel button
        if prompt_msg_id and message.bot:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=f"{error_msg}\n\n{get_text('add_search_prompt', lang)}",
                    reply_markup=cancel_kb(lang=lang),
                )
            except TelegramBadRequest:
                await message.answer(
                    f"{error_msg}\n\n{get_text('add_search_prompt', lang)}",
                    reply_markup=cancel_kb(lang=lang),
                )
        else:
            await message.answer(
                f"{error_msg}\n\n{get_text('add_search_prompt', lang)}",
                reply_markup=cancel_kb(lang=lang),
            )
        return

    await state.clear()
    await _process_add_url(
        message=message,
        url=url,
        session_factory=session_factory,
        edit_msg_id=prompt_msg_id,
        lang=lang,
    )


# ------------------------------------------------------------------ #
# Core add logic (shared by command and FSM)                           #
# ------------------------------------------------------------------ #


async def _process_add_url(
    message: Message,
    url: str,
    session_factory: sessionmaker[Session],
    edit_msg_id: int | None = None,
    lang: str = "lv",
) -> None:
    error_code = _validate_ss_url(url)
    if error_code:
        await _reply(message, get_text("err_invalid_url", lang), edit_msg_id=edit_msg_id, lang=lang)
        return

    raw_filters = extract_filters_from_url(url)
    normalized = normalize_filters(raw_filters)
    b_url = base_url_without_query(url)
    eff_url = build_effective_url(b_url, normalized) if normalized else url
    filters_json_str = filters_to_json(normalized)

    # Discover schema for human-readable filter display (best-effort)
    schema: dict = {}
    try:
        parser = SSParser()
        schema = await parser.discover_available_filters(url)
    except Exception as exc:
        logger.warning("add_search: could not discover filters for %s — %s", b_url, exc)

    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await _reply(message, get_text("err_no_user", lang), edit_msg_id=edit_msg_id, lang=lang)
        return

    # Check duplicate
    session = session_factory()
    try:
        repo = SearchRepository(session)
        existing = repo.find_by_base_url(user_id, b_url)
        if existing:
            text = get_text("err_duplicate_url", lang, sid=existing.id)
            from app.bot.keyboards.searches import error_kb
            if edit_msg_id and message.bot:
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=edit_msg_id,
                        text=text,
                        reply_markup=error_kb(back_search_id=existing.id, lang=lang),
                    )
                    return
                except TelegramBadRequest:
                    pass
            await message.answer(text, reply_markup=error_kb(back_search_id=existing.id, lang=lang))
            return

        category = detect_category(url)
        search = repo.add_search(
            user_id=user_id,
            url=url,
            title=category,
            base_url=b_url,
            filters_json=filters_json_str,
            effective_url=eff_url,
        )
        search_id = search.id
    finally:
        session.close()

    category_label = CATEGORY_LABELS.get(category, category)
    lines = [
        f"✅ <b>#{search_id}</b> — {category_label}",
        f"🔗 {eff_url}",
    ]
    if normalized:
        filter_lines = _format_filters(normalized, schema)
        lines.append(get_text("search_detail_active_filters", lang))
        lines.extend(filter_lines)
    else:
        lines.append(get_text("search_detail_no_filters", lang))

    text = "\n".join(lines)
    kb = after_add_kb(search_id, lang=lang)

    if edit_msg_id and message.bot:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=edit_msg_id,
                text=text,
                reply_markup=kb,
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


async def _reply(
    message: Message,
    text: str,
    edit_msg_id: int | None = None,
    reply_markup=None,
    lang: str = "lv",
) -> None:
    from app.bot.keyboards.searches import error_kb

    kb = reply_markup or error_kb(lang=lang)
    if edit_msg_id and message.bot:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=edit_msg_id,
                text=text,
                reply_markup=kb,
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)
