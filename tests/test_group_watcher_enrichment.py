from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Config
from app.services.group_watcher import GroupWatcherService
from app.services.ss_parser import Listing


@pytest.mark.asyncio
async def test_group_watcher_enriches_listing_before_send():
    parser = MagicMock()
    raw = Listing(external_id="101", title="A", url="https://ss.lv/msg/101/")
    enriched = Listing(
        external_id="101",
        title="A",
        url="https://ss.lv/msg/101/",
        district="Centrs",
    )
    parser.fetch_and_enrich_listing = AsyncMock(return_value=enriched)

    service = GroupWatcherService(
        session_factory=MagicMock(),
        parser=parser,
        bot=MagicMock(),
        config=Config(
            telegram_bot_token="x",
            broadcast_enabled=True,
            broadcast_chat_id=-1001,
            thread_ire_riga=1,
            thread_sell_riga=2,
            thread_auto_riga=3,
            thread_other_cities=4,
        ),
    )
    service._send_group_notification = AsyncMock()
    repo = MagicMock()
    search = SimpleNamespace(id=1, last_seen_external_id="100", route_key="other")

    await service._process_listings(repo=repo, search=search, listings=[raw])

    parser.fetch_and_enrich_listing.assert_awaited_once_with(raw)
    service._send_group_notification.assert_awaited_once()
    assert service._send_group_notification.call_args.kwargs["listing"] == enriched


@pytest.mark.asyncio
async def test_group_watcher_uses_isolated_session_and_rolls_back_failed_search():
    list_session = MagicMock()
    task_session = MagicMock()
    session_factory = MagicMock(side_effect=[list_session, task_session])

    list_repo = MagicMock()
    list_repo.get_active_group_searches.return_value = [SimpleNamespace(id=7)]
    task_repo = MagicMock()
    task_repo.get_group_search_by_id.return_value = SimpleNamespace(
        id=7,
        is_active=True,
        url="https://www.ss.lv/lv/real-estate/flats/riga/",
        effective_url=None,
    )

    coordinator = MagicMock()
    coordinator.fetch_listings = AsyncMock(side_effect=RuntimeError("fetch failed"))

    service = GroupWatcherService(
        session_factory=session_factory,
        parser=MagicMock(),
        bot=MagicMock(),
        config=Config(telegram_bot_token="x"),
        coordinator=coordinator,
    )

    with patch(
        "app.services.group_watcher.GroupSearchRepository",
        side_effect=[list_repo, task_repo],
    ):
        await service.check_all()

    assert session_factory.call_count == 2
    list_session.close.assert_called_once()
    task_session.rollback.assert_called_once()
    task_session.close.assert_called_once()
