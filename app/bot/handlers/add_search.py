"""AddSearchFSM: multi-step flow for adding a new search via URL input."""
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import BrandFixCB, MenuCB, SubCB
from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.filters import cancel_kb
from app.bot.keyboards.searches import after_add_kb
from app.bot.states import AddSearchFSM
from app.bot.utils import try_delete_message
from app.db.repo import SearchRepository, SubscriptionRepository
from app.i18n import get_text, translate_category
from app.services.filters import (
    base_url_without_query,
    build_effective_url,
    extract_filters_from_url,
    filter_display_label,
    filter_value_label,
    filters_to_json,
    normalize_filters,
    sanitize_personal_ui_text,
)
from app.services.ss_parser import SSParser, detect_category
from app.filters.profiles import detect_profile
from app.filters.renderer import render_canonical_filters

logger = logging.getLogger(__name__)
router = Router()


_ALLOWED_SS_HOSTS = {
    "ss.lv", "www.ss.lv", "m.ss.lv",
    "ss.com", "www.ss.com", "m.ss.com",
}


def _normalize_ss_url(url: str) -> str:
    """Normalize SS.lv URL variants: mobile m. host -> www. (different HTML)."""
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"m.ss.lv", "m.ss.com"}:
        return url.replace(f"//{parsed.netloc}", f"//www.{host[2:]}", 1)
    return url


_BRAND_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
_MODEL_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
_CARS_BRAND_RAW_KEY = "opt[14]"
_CARS_MODEL_RAW_KEY = "opt[15]"


def _extract_cars_path_slugs(url: str) -> tuple[str | None, str | None]:
    """Return (brand_slug, model_slug) from a /transport/cars/{brand}/{model}/ path."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    try:
        idx = parts.index("cars")
    except ValueError:
        return None, None
    brand = parts[idx + 1] if len(parts) > idx + 1 else None
    model = parts[idx + 2] if len(parts) > idx + 2 else None
    if brand and not _BRAND_SLUG_RE.fullmatch(brand):
        brand = None
    if model and not _MODEL_SLUG_RE.fullmatch(model):
        model = None
    return brand, model


def _strip_query_keys(url: str, keys: set[str]) -> str:
    parsed = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k not in keys]
    return urlunparse(parsed._replace(query=urlencode(kept)))


def _brand_conflict_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_replace_brand", lang), callback_data=BrandFixCB(choice="url"))
    b.button(text=get_text("btn_keep_brand", lang), callback_data=BrandFixCB(choice="keep"))
    b.adjust(1)
    return b.as_markup()


def _limit_reached_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_buy_more_searches", lang), callback_data=SubCB(action="show"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def _resolve_cars_brand_from_url(url: str) -> tuple[str, str, str | None, str | None]:
    """Reconcile brand in URL path vs query filters.

    Returns (status, url, path_brand, query_brand):
      - ("ok", possibly-updated-url, applied_brand|None, None) — no conflict;
        brand/model from path merged into query when query had none.
      - ("conflict", url, path_brand, query_brand) — caller must ask the user.
    """
    path_brand, path_model = _extract_cars_path_slugs(url)
    if not path_brand:
        return "ok", url, None, None
    filters = extract_filters_from_url(url)
    q_brand_raw = filters.get(_CARS_BRAND_RAW_KEY)
    q_brand = str(q_brand_raw).strip().lower() if q_brand_raw else None
    if q_brand and _BRAND_SLUG_RE.fullmatch(q_brand) and q_brand != path_brand:
        return "conflict", url, path_brand, q_brand
    # No query brand (or same / non-slug legacy value): path brand wins.
    parsed = urlparse(url)
    params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in {_CARS_BRAND_RAW_KEY, _CARS_MODEL_RAW_KEY}
    ]
    params.append((_CARS_BRAND_RAW_KEY, path_brand))
    if path_model:
        params.append((_CARS_MODEL_RAW_KEY, path_model))
    new_url = urlunparse(parsed._replace(query=urlencode(params)))
    applied = path_brand if q_brand != path_brand else None
    return "ok", new_url, applied, None


def _validate_ss_url(url: str) -> str | None:
    """Return None if valid, or a human-readable error string (language-agnostic)."""
    url = url.strip()
    if not url:
        return "empty"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "bad_scheme"
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_SS_HOSTS:
        return "bad_domain"
    return None


def _format_filters(normalized: dict, schema: dict, lang: str, profile: str | None = None) -> list[str]:
    lines = []
    for key, value in normalized.items():
        label = filter_display_label(key, schema=schema, locale=lang, profile=profile)
        display_value = filter_value_label(key, value, locale=lang, profile=profile, schema=schema)
        lines.append(
            sanitize_personal_ui_text(f"  • {label}: {display_value}", locale=lang, profile=profile)
        )
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

    # Cars: brand in URL path vs brand already set in query — ask if they differ.
    norm_url = _normalize_ss_url(url)
    if detect_profile(norm_url) == "cars":
        status, resolved_url, _applied, q_brand = _resolve_cars_brand_from_url(norm_url)
        if status == "conflict":
            path_brand, _ = _extract_cars_path_slugs(norm_url)
            await state.set_state(AddSearchFSM.waiting_brand_choice)
            await state.update_data(pending_url=norm_url, prompt_msg_id=prompt_msg_id)
            question = get_text(
                "brand_conflict_question", lang,
                url_brand=(path_brand or "").capitalize(),
                filter_brand=(q_brand or "").capitalize(),
            )
            kb = _brand_conflict_kb(lang)
            if prompt_msg_id and message.bot:
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id, message_id=prompt_msg_id,
                        text=question, reply_markup=kb,
                    )
                    return
                except TelegramBadRequest:
                    pass
            await message.answer(question, reply_markup=kb)
            return
        url = resolved_url

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
    user_id: int | None = None,
) -> None:
    error_code = _validate_ss_url(url)
    if error_code:
        await _reply(message, get_text("err_invalid_url", lang), edit_msg_id=edit_msg_id, lang=lang)
        return
    url = _normalize_ss_url(url)

    brand_note: str | None = None
    if detect_profile(url) == "cars":
        status, resolved_url, applied_brand, _ = _resolve_cars_brand_from_url(url)
        # Non-FSM entry point: on conflict the path brand wins silently.
        url = resolved_url
        if status == "conflict":
            path_brand, _pm = _extract_cars_path_slugs(url)
            _st, url, applied_brand, _ = _resolve_cars_brand_from_url(
                _strip_query_keys(url, {_CARS_BRAND_RAW_KEY, _CARS_MODEL_RAW_KEY})
            )
        if applied_brand:
            brand_note = get_text("brand_from_url_applied", lang, brand=applied_brand.capitalize())

    raw_filters = extract_filters_from_url(url)
    normalized = normalize_filters(raw_filters)
    b_url = base_url_without_query(url)
    eff_url = build_effective_url(b_url, normalized) if normalized else url
    filters_json_str = filters_to_json(normalized)
    profile = detect_profile(url)

    # Discover schema for human-readable filter display (best-effort)
    schema: dict = {}
    try:
        parser = SSParser()
        schema = await parser.discover_available_filters(url)
    except Exception as exc:
        logger.warning("add_search: could not discover filters for %s — %s", b_url, exc)

    if user_id is None:
        user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await _reply(message, get_text("err_no_user", lang), edit_msg_id=edit_msg_id, lang=lang)
        return

    # Check duplicate: same link is allowed as long as the filters differ
    session = session_factory()
    try:
        repo = SearchRepository(session)
        existing = repo.find_duplicate(user_id, b_url, filters_json_str)
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
        sub_repo = SubscriptionRepository(session)
        limit = sub_repo.active_search_limit(user_id)
        active_count = repo.count_active_for_user(user_id)
        if active_count >= limit:
            text = get_text("err_search_limit", lang, limit=limit)
            kb = _limit_reached_kb(lang)
            if edit_msg_id and message.bot:
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id, message_id=edit_msg_id,
                        text=text, reply_markup=kb,
                    )
                    return
                except TelegramBadRequest:
                    pass
            await message.answer(text, reply_markup=kb)
            return
        search = repo.add_search(
            user_id=user_id,
            url=url,
            title=category,
            base_url=b_url,
            filters_json=filters_json_str,
            effective_url=eff_url,
            category_profile=profile,
        )
        search_id = search.id
    finally:
        session.close()

    category_label = translate_category(category, lang)
    lines = [
        f"✅ <b>#{search_id}</b> — {category_label}",
        get_text("search_detail_url", lang, url=b_url),
    ]
    if normalized:
        # Use profile-aware renderer; fall back to schema-based for generic
        if profile:
            filter_lines = render_canonical_filters(normalized, profile, locale=lang)
        else:
            filter_lines = _format_filters(normalized, schema, lang, profile=profile)
        lines.append(get_text("search_detail_active_filters", lang))
        lines.extend(filter_lines)
    else:
        lines.append(get_text("search_detail_no_filters", lang))
    if brand_note:
        lines.append(brand_note)

    text = sanitize_personal_ui_text("\n".join(lines), locale=lang, profile=profile)
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


# ------------------------------------------------------------------ #
# Brand conflict resolution (URL path vs query filter)                #
# ------------------------------------------------------------------ #


@router.callback_query(BrandFixCB.filter(), AddSearchFSM.waiting_brand_choice)
async def cb_brand_fix(
    callback: CallbackQuery,
    callback_data: BrandFixCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await callback.answer()
    data = await state.get_data()
    pending_url: str | None = data.get("pending_url")
    prompt_msg_id: int | None = data.get("prompt_msg_id")
    await state.clear()

    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    if not pending_url or not callback.message:
        return

    if callback_data.choice == "url":
        # Link brand wins: drop query brand/model, path fills them in.
        url = _strip_query_keys(pending_url, {_CARS_BRAND_RAW_KEY, _CARS_MODEL_RAW_KEY})
        _st, url, _applied, _ = _resolve_cars_brand_from_url(url)
    else:
        # Keep filter brand: rewrite path to it, drop incompatible model.
        from app.bot.handlers.filter_cmds import _rewrite_cars_brand_slug_in_url
        filters = extract_filters_from_url(pending_url)
        q_brand = str(filters.get(_CARS_BRAND_RAW_KEY, "")).strip().lower()
        url = _strip_query_keys(pending_url, {_CARS_MODEL_RAW_KEY})
        url = _rewrite_cars_brand_slug_in_url(url, q_brand)

    await _process_add_url(
        message=callback.message,
        url=url,
        session_factory=session_factory,
        edit_msg_id=prompt_msg_id or callback.message.message_id,
        lang=lang,
        user_id=user_id,
    )
