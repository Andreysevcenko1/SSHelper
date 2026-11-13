from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
import app.services.group_watcher as gw
from app.services.group_watcher import GroupWatcherService
from app.services.ss_parser import Listing


@pytest.mark.asyncio
async def test_same_listing_from_overlapping_group_searches_posts_once(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    config = SimpleNamespace(broadcast_chat_id=-100, facebook_enabled=False)
    coordinator = MagicMock()
    coordinator.enrich_listing = AsyncMock(side_effect=lambda x: x)
    service = GroupWatcherService(
        session_factory=factory, parser=MagicMock(), bot=MagicMock(), config=config, coordinator=coordinator
    )
    service._send_group_notification = AsyncMock()
    monkeypatch.setattr(gw, "_thread_id_for_route_key", lambda *_: 7)

    new = Listing(external_id="n1", title="Flat", url="https://www.ss.lv/msg/lv/x/n1.html")
    old = Listing(external_id="o1", title="old", url="https://www.ss.lv/msg/lv/x/o1.html")
    for sid in (1, 2):
        search = SimpleNamespace(
            id=sid, last_seen_external_id="o1", route_key="flats_riga",
            effective_url="https://www.ss.lv/lv/real-estate/flats/riga/", url="",
        )
        await service._process_listings(repo=MagicMock(), search=search, listings=[new, old])

    assert service._send_group_notification.await_count == 1
