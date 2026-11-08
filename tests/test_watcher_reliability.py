from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.watcher import WatcherService


@pytest.mark.asyncio
async def test_personal_watcher_isolates_and_rolls_back_failed_search_session():
    list_session = MagicMock()
    task_session = MagicMock()
    session_factory = MagicMock(side_effect=[list_session, task_session])

    list_repo = MagicMock()
    list_repo.get_active_searches.return_value = [SimpleNamespace(id=9)]
    task_repo = MagicMock()
    task_repo.get_by_id.return_value = SimpleNamespace(
        id=9,
        is_active=True,
        url="https://www.ss.lv/lv/real-estate/flats/riga/",
        effective_url=None,
    )

    coordinator = MagicMock()
    coordinator.fetch_listings = AsyncMock(side_effect=RuntimeError("fetch failed"))
    service = WatcherService(
        session_factory=session_factory,
        parser=MagicMock(),
        bot=MagicMock(),
        coordinator=coordinator,
    )
    service._enforce_limits = AsyncMock()

    with patch(
        "app.services.watcher.SearchRepository",
        side_effect=[list_repo, task_repo],
    ):
        await service.check_all()

    service._enforce_limits.assert_awaited_once_with(list_session, list_repo)
    assert session_factory.call_count == 2
    list_session.close.assert_called_once()
    task_session.rollback.assert_called_once()
    task_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_limit_enforcement_never_pauses_admin_searches():
    session = MagicMock()
    repo = MagicMock()
    repo.get_active_searches.return_value = [
        SimpleNamespace(id=1, user_id=42),
        SimpleNamespace(id=2, user_id=42),
    ]
    config = SimpleNamespace(admin_user_ids=[42], broadcast_enabled=False)
    service = WatcherService(
        session_factory=MagicMock(),
        parser=MagicMock(),
        bot=MagicMock(),
        config=config,
    )

    with patch("app.services.watcher.SubscriptionRepository") as sub_repo_cls:
        sub_repo_cls.return_value.active_search_limit.return_value = None
        await service._enforce_limits(session, repo)

    sub_repo_cls.return_value.active_search_limit.assert_called_once_with(42, [42])
    repo.pause_search.assert_not_called()


@pytest.mark.asyncio
async def test_personal_notifications_go_only_to_search_owner():
    from app.services.ss_parser import Listing

    new = Listing(external_id="n1", title="Audi A4", url="https://www.ss.lv/msg/x.html", price="9 000 €")
    old = Listing(external_id="o1", title="old", url="https://www.ss.lv/msg/o.html")

    def make_search(sid, user_id, filters_json):
        return SimpleNamespace(
            id=sid, user_id=user_id, last_seen_external_id="o1",
            filters_json=filters_json, category_profile="cars",
            effective_url="https://www.ss.lv/lv/transport/cars/", url="https://www.ss.lv/lv/transport/cars/",
        )

    coordinator = MagicMock()
    coordinator.enrich_listing = AsyncMock(side_effect=lambda x: x)
    service = WatcherService(
        session_factory=MagicMock(),
        parser=MagicMock(),
        bot=MagicMock(),
        coordinator=coordinator,
        config=SimpleNamespace(broadcast_enabled=False),
    )
    service._resolve_user_lang = MagicMock(return_value="lv")
    service._send_notification = AsyncMock()
    repo = MagicMock()
    repo.display_no.return_value = 1

    for search in (make_search(1, 111, None), make_search(2, 222, None)):
        await service._process_listings(repo=repo, search=search, listings=[new, old])

    chat_ids = [c.kwargs["chat_id"] for c in service._send_notification.await_args_list]
    assert chat_ids == [111, 222]
