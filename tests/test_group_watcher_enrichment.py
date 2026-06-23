from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
