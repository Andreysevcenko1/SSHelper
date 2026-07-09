"""Subscription screen + Telegram Stars payments for extra search slots."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import MenuCB, SubCB
from app.bot.handlers.common import get_user_lang
from app.config import Config
from app.db.repo import SearchRepository, SubscriptionRepository
from app.i18n import get_text
from app.services.plans import PLAN_DURATION_DAYS, PLANS

logger = logging.getLogger(__name__)

router = Router()

_PAYLOAD_PREFIX = "sshelper_sub:"


def subscription_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for plan in PLANS.values():
        b.button(
            text=get_text(plan.label_i18n_key, lang, eur=plan.price_eur, stars=plan.price_stars),
            callback_data=SubCB(action="buy", plan=plan.plan_id),
        )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def _status_text(user_id: int, lang: str, session_factory: sessionmaker[Session]) -> str:
    session = session_factory()
    try:
        sub_repo = SubscriptionRepository(session)
        sub = sub_repo.get_active(user_id)
        limit = sub_repo.active_search_limit(user_id)
        active = SearchRepository(session).count_active_for_user(user_id)
    finally:
        session.close()

    lines = [get_text("sub_screen_title", lang)]
    if sub is not None:
        from datetime import datetime
        days_left = max(0, (sub.expires_at - datetime.utcnow()).days)
        plan = PLANS.get(sub.plan)
        plan_name = (
            get_text(plan.label_i18n_key, lang, eur=plan.price_eur, stars=plan.price_stars)
            if plan else sub.plan
        )
        lines.append(get_text("sub_status_active", lang, plan=plan_name, days=days_left))
    else:
        lines.append(get_text("sub_status_free", lang))
    lines.append(get_text("sub_usage", lang, active=active, limit=limit))
    lines.append("")
    lines.append(get_text("sub_pick_plan", lang))
    return "\n".join(lines)


@router.callback_query(SubCB.filter(F.action == "show"))
async def cb_sub_show(
    callback: CallbackQuery,
    callback_data: SubCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"
    if user_id is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(
            _status_text(user_id, lang, session_factory),
            reply_markup=subscription_kb(lang),
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(SubCB.filter(F.action == "buy"))
async def cb_sub_buy(
    callback: CallbackQuery,
    callback_data: SubCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    plan = PLANS.get(callback_data.plan or "")
    if plan is None or callback.message is None:
        await callback.answer()
        return

    title = get_text("sub_invoice_title", lang, total=plan.total_searches)
    description = get_text(
        "sub_invoice_desc", lang,
        extra=plan.extra_searches, total=plan.total_searches,
        days=PLAN_DURATION_DAYS, eur=plan.price_eur,
    )
    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=f"{_PAYLOAD_PREFIX}{plan.plan_id}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=plan.price_stars)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    payload = pre_checkout_query.invoice_payload or ""
    ok = payload.startswith(_PAYLOAD_PREFIX) and payload[len(_PAYLOAD_PREFIX):] in PLANS
    await pre_checkout_query.answer(ok=ok, error_message="Unknown plan" if not ok else None)


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    payload = (message.successful_payment.invoice_payload or "") if message.successful_payment else ""
    plan = PLANS.get(payload[len(_PAYLOAD_PREFIX):]) if payload.startswith(_PAYLOAD_PREFIX) else None
    if user_id is None or plan is None:
        logger.warning("payment: unexpected payload %r from user %s", payload, user_id)
        return

    session = session_factory()
    try:
        sub_repo = SubscriptionRepository(session)
        sub_repo.set_plan(user_id, plan.plan_id, plan.extra_searches, days=PLAN_DURATION_DAYS)
        limit = sub_repo.active_search_limit(user_id)
    finally:
        session.close()

    logger.info(
        "payment: user %s bought plan %s (%d stars), new limit=%d",
        user_id, plan.plan_id, plan.price_stars, limit,
    )
    await message.answer(
        get_text("sub_paid_ok", lang, total=plan.total_searches, days=PLAN_DURATION_DAYS)
    )


# ------------------------------------------------------------------ #
# Admin: /stars — bot Stars balance & recent transactions             #
# ------------------------------------------------------------------ #


@router.message(Command("stars"))
async def cmd_stars(message: Message, config: Config) -> None:
    if message.from_user is None or message.from_user.id not in config.admin_user_ids:
        return
    if message.bot is None:
        return
    try:
        result = await message.bot.get_star_transactions(limit=20)
    except Exception as exc:
        logger.warning("stars: failed to fetch transactions: %s", exc)
        await message.answer(f"⚠️ Не удалось получить транзакции: {exc}")
        return

    txs = result.transactions or []
    income = 0
    lines: list[str] = []
    for tx in txs:
        sign = "+" if tx.source is not None else "-"
        if tx.source is not None:
            income += tx.amount
        when = tx.date.strftime("%d.%m %H:%M") if tx.date else "?"
        lines.append(f"{sign}{tx.amount} ⭐  ({when})")

    header = f"⭐ Транзакций (последние {len(txs)}): приход {income} ⭐"
    body = "\n".join(lines) if lines else "Пока нет транзакций."
    await message.answer(f"{header}\n\n{body}")
