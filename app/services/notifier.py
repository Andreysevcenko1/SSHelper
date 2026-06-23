"""
Shared notification sender for SS.lv listings.

Used by both :mod:`app.services.watcher` (individual DMs) and
:mod:`app.services.group_watcher` (group forum topics) so that image-quality
policy and structured logging live in one place.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from app.services.formatter import detect_deal_type, select_image_url

if TYPE_CHECKING:
    from app.services.ss_parser import Listing

logger = logging.getLogger(__name__)

_MAX_CAPTION_LEN = 1024  # Telegram sendPhoto caption limit

# Fields logged to measure parse quality per notification
_METADATA_FIELDS = (
    "district",
    "street",
    "rooms",
    "area_m2",
    "floor_current",
    "house_type",
    "price_total_eur",
    "price_per_m2_eur",
    "price_monthly_eur",
)


def _template_name(deal_type: str) -> str:
    if deal_type == "sell":
        return "sell"
    if deal_type == "rent":
        return "rent"
    return "generic"


def _present_fields(listing: "Listing") -> list[str]:
    """Return a list of non-None metadata field names for *listing*."""
    return [f for f in _METADATA_FIELDS if getattr(listing, f, None) is not None]


async def send_listing_notification(
    bot: Bot,
    chat_id: int,
    listing: "Listing",
    text: str,
    reply_markup: InlineKeyboardMarkup,
    *,
    thread_id: int | None = None,
) -> tuple[str, int | None]:
    """Send *listing* to *chat_id* (optionally into forum *thread_id*).

    Image policy
    ------------
    * Tries to send the HD / upgraded image URL returned by
      :func:`~app.services.formatter.select_image_url`.
    * On failure (or when no HD URL is available) falls back to a plain text
      message — **never** retries with a low-resolution thumbnail.

    Logging
    -------
    Emits one INFO line per sent message that includes:
    ``listing_id``, ``deal_type``, ``template_used``, ``fields_present``,
    ``image_mode`` (``hd`` | ``text_only``), ``chat_id``, ``thread_id``,
    ``message_id``.

    Returns
    -------
    ``(image_mode, message_id)`` — ``image_mode`` is ``"hd"`` or
    ``"text_only"``; ``message_id`` may be ``None`` on unexpected errors.
    """
    deal_type = listing.deal_type
    template = _template_name(deal_type)
    fields_present = _present_fields(listing)
    hd_url = select_image_url(listing)

    # Truncate caption to Telegram's limit (applies to both photo and text)
    caption = text if len(text) <= _MAX_CAPTION_LEN else text[: _MAX_CAPTION_LEN - 1] + "…"

    logger.debug(
        "send_listing_notification: listing=%s deal_type=%s template=%s "
        "fields=%s has_hd=%s chat=%s thread=%s",
        listing.external_id,
        deal_type,
        template,
        fields_present,
        hd_url is not None,
        chat_id,
        thread_id,
    )

    extra_kwargs: dict = {}
    if thread_id is not None:
        extra_kwargs["message_thread_id"] = thread_id

    if hd_url:
        try:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=hd_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                **extra_kwargs,
            )
            image_mode = "hd"
            logger.info(
                "Sent listing=%s deal_type=%s template=%s fields=%s "
                "image_mode=%s chat=%s thread=%s message_id=%s",
                listing.external_id,
                deal_type,
                template,
                fields_present,
                image_mode,
                chat_id,
                thread_id,
                msg.message_id,
            )
            return image_mode, msg.message_id
        except Exception as exc:
            logger.warning(
                "send_photo failed for listing=%s (%s) — falling back to text_only",
                listing.external_id,
                exc,
            )

    # Text-only fallback (HD unavailable or send failed)
    msg = await bot.send_message(
        chat_id=chat_id,
        text=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
        **extra_kwargs,
    )
    image_mode = "text_only"
    logger.info(
        "Sent listing=%s deal_type=%s template=%s fields=%s "
        "image_mode=%s chat=%s thread=%s message_id=%s",
        listing.external_id,
        deal_type,
        template,
        fields_present,
        image_mode,
        chat_id,
        thread_id,
        msg.message_id,
    )
    return image_mode, msg.message_id
