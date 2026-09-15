"""Tests for Facebook Page auto-posting (Graph API) and its wiring into group_watcher."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Config
from app.services.facebook_publisher import publish_to_facebook_page
from app.services.group_watcher import GroupWatcherService, _to_facebook_text
from app.services.ss_parser import Listing


def _fb_config(**overrides) -> Config:
    base = dict(
        telegram_bot_token="x",
        facebook_enabled=True,
        facebook_page_id="1234567890",
        facebook_page_access_token="EAABtoken",
    )
    base.update(overrides)
    return Config(**base)


# ------------------------------------------------------------------ #
# _to_facebook_text                                                    #
# ------------------------------------------------------------------ #


def test_to_facebook_text_strips_html_tags():
    html_text = "<b>Pilsēta: Rīga</b>\nCena: 430 €/mēn."
    plain = _to_facebook_text(html_text, "https://www.ss.lv/msg/lv/x.html")
    assert "<b>" not in plain
    assert "</b>" not in plain
    assert "Pilsēta: Rīga" in plain


def test_to_facebook_text_unescapes_html_entities():
    html_text = "Cena: 430 &euro;/m&#232;n."
    plain = _to_facebook_text(html_text, "https://www.ss.lv/msg/lv/x.html")
    assert "&euro;" not in plain
    assert "&#232;" not in plain


def test_to_facebook_text_appends_url_when_missing():
    html_text = "Pilsēta: Rīga"
    url = "https://www.ss.lv/msg/lv/x.html"
    plain = _to_facebook_text(html_text, url)
    assert url in plain


def test_to_facebook_text_does_not_duplicate_url():
    url = "https://www.ss.lv/msg/lv/x.html"
    html_text = f"Pilsēta: Rīga\nSaite: {url}"
    plain = _to_facebook_text(html_text, url)
    assert plain.count(url) == 1


# ------------------------------------------------------------------ #
# publish_to_facebook_page                                             #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_publish_disabled_returns_false():
    config = _fb_config(facebook_enabled=False)
    result = await publish_to_facebook_page(config, "hello", listing_id="1")
    assert result is False


@pytest.mark.asyncio
async def test_publish_missing_credentials_returns_false():
    config = _fb_config(facebook_page_id=None)
    result = await publish_to_facebook_page(config, "hello", listing_id="1")
    assert result is False


@pytest.mark.asyncio
async def test_publish_text_only_success():
    config = _fb_config()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"id": "123_456"})

    mock_post_cm = MagicMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.facebook_publisher.aiohttp.ClientSession", return_value=mock_session_cm):
        result = await publish_to_facebook_page(config, "Pilsēta: Rīga", listing_id="hiofx")

    assert result is True
    called_url = mock_session.post.call_args.args[0]
    assert "/feed" in called_url
    payload = mock_session.post.call_args.kwargs["data"]
    assert payload["message"] == "Pilsēta: Rīga"
    assert payload["access_token"] == "EAABtoken"


@pytest.mark.asyncio
async def test_publish_with_image_uses_photos_endpoint():
    config = _fb_config()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"post_id": "123_789"})

    mock_post_cm = MagicMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.facebook_publisher.aiohttp.ClientSession", return_value=mock_session_cm):
        result = await publish_to_facebook_page(
            config, "Pilsēta: Rīga", image_url="https://img.example/1.jpg", listing_id="hiofx"
        )

    assert result is True
    called_url = mock_session.post.call_args.args[0]
    assert "/photos" in called_url
    payload = mock_session.post.call_args.kwargs["data"]
    assert payload["url"] == "https://img.example/1.jpg"
    assert payload["caption"] == "Pilsēta: Rīga"


@pytest.mark.asyncio
async def test_publish_graph_api_error_returns_false():
    config = _fb_config()

    mock_resp = AsyncMock()
    mock_resp.status = 400
    mock_resp.json = AsyncMock(return_value={"error": {"message": "Invalid token"}})

    mock_post_cm = MagicMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.facebook_publisher.aiohttp.ClientSession", return_value=mock_session_cm):
        result = await publish_to_facebook_page(config, "hello", listing_id="1")

    assert result is False


@pytest.mark.asyncio
async def test_publish_network_exception_returns_false():
    config = _fb_config()
    with patch("app.services.facebook_publisher.aiohttp.ClientSession", side_effect=RuntimeError("boom")):
        result = await publish_to_facebook_page(config, "hello", listing_id="1")
    assert result is False


# ------------------------------------------------------------------ #
# GroupWatcherService integration                                      #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_group_watcher_posts_to_facebook_when_enabled():
    config = _fb_config(
        broadcast_enabled=True,
        broadcast_chat_id=-1001,
        thread_ire_riga=1,
        thread_sell_riga=2,
        thread_auto_riga=3,
        thread_other_cities=4,
    )
    service = GroupWatcherService(
        session_factory=MagicMock(),
        parser=MagicMock(),
        bot=MagicMock(),
        config=config,
    )
    listing = Listing(external_id="hiofx", title="A", url="https://ss.lv/msg/hiofx.html", city="Rīga")

    with patch("app.services.group_watcher.send_listing_notification", new=AsyncMock(return_value=("text", 1))), \
         patch("app.services.group_watcher.publish_to_facebook_page", new=AsyncMock(return_value=True)) as fb_mock:
        await service._send_group_notification(chat_id=-1001, thread_id=1, listing=listing)

    fb_mock.assert_awaited_once()
    assert fb_mock.call_args.kwargs["listing_id"] == "hiofx"


@pytest.mark.asyncio
async def test_group_watcher_skips_facebook_when_disabled():
    config = Config(
        telegram_bot_token="x",
        broadcast_enabled=True,
        broadcast_chat_id=-1001,
        thread_ire_riga=1,
        thread_sell_riga=2,
        thread_auto_riga=3,
        thread_other_cities=4,
        facebook_enabled=False,
    )
    service = GroupWatcherService(
        session_factory=MagicMock(),
        parser=MagicMock(),
        bot=MagicMock(),
        config=config,
    )
    listing = Listing(external_id="hiofx", title="A", url="https://ss.lv/msg/hiofx.html")

    with patch("app.services.group_watcher.send_listing_notification", new=AsyncMock(return_value=("text", 1))), \
         patch("app.services.group_watcher.publish_to_facebook_page", new=AsyncMock()) as fb_mock:
        await service._send_group_notification(chat_id=-1001, thread_id=1, listing=listing)

    fb_mock.assert_not_awaited()
