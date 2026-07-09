"""Tests for FetchCoordinator: dedup, caching, concurrency limits."""
import asyncio

import pytest

from app.services.fetch_coordinator import FetchCoordinator
from app.services.ss_parser import Listing


class FakeParser:
    def __init__(self):
        self.list_calls = 0
        self.detail_calls = 0
        self.concurrent = 0
        self.max_concurrent = 0

    async def fetch_listings(self, url, limit=10):
        self.list_calls += 1
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await asyncio.sleep(0.01)
        self.concurrent -= 1
        return [Listing(external_id=f"x-{url}", title="t", url=url)]

    async def fetch_and_enrich_listing(self, listing):
        self.detail_calls += 1
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await asyncio.sleep(0.01)
        self.concurrent -= 1
        return listing


@pytest.mark.asyncio
async def test_list_dedup_same_url():
    parser = FakeParser()
    coord = FetchCoordinator(parser)
    results = await asyncio.gather(
        *(coord.fetch_listings("https://ss.lv/a/") for _ in range(10))
    )
    assert parser.list_calls == 1
    assert all(r[0].external_id == "x-https://ss.lv/a/" for r in results)


@pytest.mark.asyncio
async def test_list_different_urls_fetch_separately():
    parser = FakeParser()
    coord = FetchCoordinator(parser)
    await asyncio.gather(
        coord.fetch_listings("https://ss.lv/a/"),
        coord.fetch_listings("https://ss.lv/b/"),
    )
    assert parser.list_calls == 2


@pytest.mark.asyncio
async def test_detail_dedup_same_listing():
    parser = FakeParser()
    coord = FetchCoordinator(parser)
    listing = Listing(external_id="abc", title="t", url="https://ss.lv/msg/abc.html")
    await asyncio.gather(*(coord.enrich_listing(listing) for _ in range(5)))
    assert parser.detail_calls == 1


@pytest.mark.asyncio
async def test_concurrency_bounded():
    parser = FakeParser()
    coord = FetchCoordinator(parser)
    await asyncio.gather(
        *(coord.fetch_listings(f"https://ss.lv/{i}/") for i in range(20))
    )
    assert parser.max_concurrent <= 5


@pytest.mark.asyncio
async def test_prune_clears_expired(monkeypatch):
    parser = FakeParser()
    coord = FetchCoordinator(parser)
    await coord.fetch_listings("https://ss.lv/a/")
    assert coord._list_cache
    import app.services.fetch_coordinator as fc
    monkeypatch.setattr(fc, "LIST_CACHE_TTL", 0.0)
    coord.prune()
    assert not coord._list_cache
