"""Shared fetch coordinator for the personal and group watchers.

Optimisations:
- List-page dedup: identical fetch URLs are downloaded once per cycle (TTL cache),
  so N searches watching the same link cost 1 request.
- Detail-page cache: an enriched listing is fetched once and reused across all
  searches and both watchers (TTL cache keyed by external_id).
- Bounded concurrency: at most MAX_CONCURRENCY simultaneous requests to SS.lv,
  with a small random jitter between requests to stay polite.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 5
LIST_CACHE_TTL = 60.0        # seconds; < poll interval, dedupes within a cycle
DETAIL_CACHE_TTL = 900.0     # 15 min; a listing's detail page rarely changes
JITTER_RANGE = (0.1, 0.5)    # polite delay before each outbound request


class FetchCoordinator:
    """Caches and rate-limits SS.lv fetches shared by all watcher pipelines."""

    def __init__(self, parser: SSParser) -> None:
        self.parser = parser
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        self._list_cache: dict[str, tuple[float, list[Listing]]] = {}
        self._list_locks: dict[str, asyncio.Lock] = {}
        self._detail_cache: dict[str, tuple[float, Listing]] = {}
        self._detail_locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------- lists ---

    async def fetch_listings(self, url: str, limit: int = 10) -> list[Listing]:
        now = time.monotonic()
        cached = self._list_cache.get(url)
        if cached and now - cached[0] < LIST_CACHE_TTL:
            logger.debug("FetchCoordinator: list cache hit for %s", url)
            return cached[1]

        lock = self._list_locks.setdefault(url, asyncio.Lock())
        async with lock:
            # Re-check: another task may have fetched while we waited.
            cached = self._list_cache.get(url)
            if cached and time.monotonic() - cached[0] < LIST_CACHE_TTL:
                return cached[1]
            async with self._semaphore:
                await asyncio.sleep(random.uniform(*JITTER_RANGE))
                listings = await self.parser.fetch_listings(url, limit=limit)
            self._list_cache[url] = (time.monotonic(), listings)
            return listings

    # ------------------------------------------------------------ details ---

    async def enrich_listing(self, listing: Listing) -> Listing:
        key = listing.external_id or listing.url
        if not key:
            return await self._enrich_raw(listing)

        now = time.monotonic()
        cached = self._detail_cache.get(key)
        if cached and now - cached[0] < DETAIL_CACHE_TTL:
            logger.debug("FetchCoordinator: detail cache hit for %s", key)
            return cached[1]

        lock = self._detail_locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._detail_cache.get(key)
            if cached and time.monotonic() - cached[0] < DETAIL_CACHE_TTL:
                return cached[1]
            enriched = await self._enrich_raw(listing)
            self._detail_cache[key] = (time.monotonic(), enriched)
            return enriched

    async def _enrich_raw(self, listing: Listing) -> Listing:
        async with self._semaphore:
            await asyncio.sleep(random.uniform(*JITTER_RANGE))
            return await self.parser.fetch_and_enrich_listing(listing)

    # ------------------------------------------------------------ hygiene ---

    def prune(self) -> None:
        """Drop expired cache entries and orphaned locks (called per cycle)."""
        now = time.monotonic()
        for cache, ttl, locks in (
            (self._list_cache, LIST_CACHE_TTL, self._list_locks),
            (self._detail_cache, DETAIL_CACHE_TTL, self._detail_locks),
        ):
            expired = [k for k, (ts, _) in cache.items() if now - ts >= ttl]
            for k in expired:
                cache.pop(k, None)
                locks.pop(k, None)
