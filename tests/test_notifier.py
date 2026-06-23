"""Tests for app.services.notifier — shared send function, image-mode logging,
group/individual formatter identity."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ss_parser import Listing
from app.services.notifier import send_listing_notification, _template_name, _present_fields
import app.services.notifier as notifier_module
import app.services.formatter as formatter_module
import app.services.watcher as watcher_module
import app.services.group_watcher as group_watcher_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _listing(**kwargs) -> Listing:
    defaults = dict(
        external_id="99999",
        title="Test listing",
        url="https://ss.lv/msg/lv/real-estate/flats/riga/sell/99999/",
        deal_type="sell",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


def _make_bot(send_photo_result=None, send_message_result=None, send_photo_side_effect=None):
    bot = MagicMock()
    if send_photo_side_effect is not None:
        bot.send_photo = AsyncMock(side_effect=send_photo_side_effect)
    else:
        photo_msg = MagicMock()
        photo_msg.message_id = 42
        bot.send_photo = AsyncMock(return_value=send_photo_result or photo_msg)
    text_msg = MagicMock()
    text_msg.message_id = 99
    bot.send_message = AsyncMock(return_value=send_message_result or text_msg)
    return bot


def _make_kb():
    from aiogram.types import InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[])


# ---------------------------------------------------------------------------
# _template_name
# ---------------------------------------------------------------------------

class TestTemplateName:
    def test_sell(self):
        assert _template_name("sell") == "sell"

    def test_rent(self):
        assert _template_name("rent") == "rent"

    def test_unknown(self):
        assert _template_name("unknown") == "generic"

    def test_other(self):
        assert _template_name("anything") == "generic"


# ---------------------------------------------------------------------------
# _present_fields
# ---------------------------------------------------------------------------

class TestPresentFields:
    def test_all_none(self):
        assert _present_fields(_listing()) == []

    def test_some_fields(self):
        listing = _listing(district="Centrs", rooms=3, price_total_eur=100000.0)
        fields = _present_fields(listing)
        assert "district" in fields
        assert "rooms" in fields
        assert "price_total_eur" in fields
        assert "street" not in fields


# ---------------------------------------------------------------------------
# send_listing_notification — HD path
# ---------------------------------------------------------------------------

class TestSendListingNotificationHD:
    @pytest.mark.asyncio
    async def test_sends_photo_when_hd_url_available(self):
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
        )
        bot = _make_bot()
        kb = _make_kb()

        image_mode, message_id = await send_listing_notification(
            bot=bot,
            chat_id=123,
            listing=listing,
            text="Test caption",
            reply_markup=kb,
        )

        assert image_mode == "hd"
        assert message_id == 42
        bot.send_photo.assert_called_once()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_passes_thread_id_to_send_photo(self):
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
        )
        bot = _make_bot()
        kb = _make_kb()

        await send_listing_notification(
            bot=bot,
            chat_id=123,
            listing=listing,
            text="Text",
            reply_markup=kb,
            thread_id=55,
        )

        call_kwargs = bot.send_photo.call_args.kwargs
        assert call_kwargs.get("message_thread_id") == 55

    @pytest.mark.asyncio
    async def test_image_mode_hd_returns_message_id(self):
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
        )
        photo_msg = MagicMock()
        photo_msg.message_id = 7
        bot = _make_bot(send_photo_result=photo_msg)
        kb = _make_kb()

        image_mode, message_id = await send_listing_notification(
            bot=bot, chat_id=1, listing=listing, text="x", reply_markup=kb
        )

        assert image_mode == "hd"
        assert message_id == 7


# ---------------------------------------------------------------------------
# send_listing_notification — no preview fallback
# ---------------------------------------------------------------------------

class TestSendListingNotificationNoPreviewFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_text_on_send_photo_failure(self):
        """When send_photo fails, must go to text — no preview retry."""
        listing = _listing(
            image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg",
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
        )
        bot = _make_bot(send_photo_side_effect=Exception("Telegram error"))
        kb = _make_kb()

        image_mode, message_id = await send_listing_notification(
            bot=bot, chat_id=1, listing=listing, text="Text", reply_markup=kb
        )

        assert image_mode == "text"
        # send_photo was called once (HD attempt), NOT twice (no preview retry)
        assert bot.send_photo.call_count == 1
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_only_when_no_hd_url(self):
        """When select_image_url returns None, send_message is used directly."""
        listing = _listing(
            image_url_hd=None,
            photo_urls=[],
            image_url_preview=None,
        )
        bot = _make_bot()
        kb = _make_kb()

        image_mode, message_id = await send_listing_notification(
            bot=bot, chat_id=1, listing=listing, text="Text", reply_markup=kb
        )

        assert image_mode == "text"
        bot.send_photo.assert_not_called()
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_only_listing_sends_preview(self):
        """Listing with only image_url_preview is sent as preview (last resort)."""
        listing = _listing(
            image_url_hd=None,
            photo_urls=[],
            image_url_preview="https://i.ss.lv/img/cl/small/abc/1.jpg",
        )
        bot = _make_bot()
        kb = _make_kb()

        image_mode, _ = await send_listing_notification(
            bot=bot, chat_id=1, listing=listing, text="Text", reply_markup=kb
        )

        assert image_mode == "preview"
        bot.send_photo.assert_called_once()


# ---------------------------------------------------------------------------
# Caption truncation
# ---------------------------------------------------------------------------

class TestCaptionTruncation:
    @pytest.mark.asyncio
    async def test_long_caption_truncated_to_1024(self):
        listing = _listing(image_url_hd="https://i.ss.lv/img/cl/large/abc/1.jpg")
        bot = _make_bot()
        kb = _make_kb()
        long_text = "x" * 2000

        await send_listing_notification(
            bot=bot, chat_id=1, listing=listing, text=long_text, reply_markup=kb
        )

        caption_sent = bot.send_photo.call_args.kwargs["caption"]
        assert len(caption_sent) <= 1024


# ---------------------------------------------------------------------------
# Formatter identity — group and individual watcher share the same function
# ---------------------------------------------------------------------------

class TestFormatterIdentity:
    def test_watcher_uses_shared_format_listing_message(self):
        """watcher.format_listing_message must be formatter.format_listing_message."""
        assert watcher_module.format_listing_message is formatter_module.format_listing_message

    def test_group_watcher_uses_shared_format_listing_message(self):
        """group_watcher.format_listing_message must be formatter.format_listing_message."""
        assert group_watcher_module.format_listing_message is formatter_module.format_listing_message

    def test_both_watchers_use_same_notifier(self):
        """Both watcher and group_watcher must use the same send_listing_notification."""
        assert watcher_module.send_listing_notification is group_watcher_module.send_listing_notification

    def test_notifier_uses_formatter_select_image_url(self):
        """notifier.select_image_url must reference formatter.select_image_url."""
        assert notifier_module.select_image_url is formatter_module.select_image_url
