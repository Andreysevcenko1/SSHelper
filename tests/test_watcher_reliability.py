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

