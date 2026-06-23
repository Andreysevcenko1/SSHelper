"""Group watcher service.

Polls GroupSearch records independently of personal user searches and posts
new listings directly to the configured forum topics (message_thread_id).
No user_id involvement at any point.
"""

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.db.models import GroupSearch
from app.db.repo import GroupSearchRepository
from app.services.formatter import format_listing_message
from app.services.notifier import send_listing_notification
from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)

_VALID_ROUTE_KEYS = {"ire_riga", "sell_riga", "auto_riga", "other"}


def _thread_id_for_route_key(route_key: str, config: Config) -> int | None:
    """Map a route_key string to the corresponding Telegram thread id.

    Returns None when the relevant thread is not configured.
    Falls back to THREAD_OTHER_CITIES for unknown/invalid keys.
    """
    mapping = {
        "ire_riga": config.thread_ire_riga,
        "sell_riga": config.thread_sell_riga,
        "auto_riga": config.thread_auto_riga,
        "other": config.thread_other_cities,
    }
    return mapping.get(route_key, config.thread_other_cities)


class GroupWatcherService:
    """Polls group searches and posts to forum topics, fully independent of user data."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        parser: SSParser,
        bot: Bot,
        config: Config,
    ) -> None:
        self.session_factory = session_factory
        self.parser = parser
        self.bot = bot
        self.config = config

    async def check_all(self) -> None:
        session = self.session_factory()
        try:
            repo = GroupSearchRepository(session)
            searches = repo.get_active_group_searches()
            logger.info("GroupWatcher: checking %d active group search(es)", len(searches))

            for search in searches:
                try:
                    fetch_url = search.effective_url or search.url
                    listings = await self.parser.fetch_listings(fetch_url, limit=10)
                    await self._process_listings(repo=repo, search=search, listings=listings)
                except Exception:
                    logger.exception(
                        "GroupWatcher: failed to process group search #%d",
                        search.id,
                    )
        finally:
            session.close()

    async def _process_listings(
        self,
        repo: GroupSearchRepository,
        search: GroupSearch,
        listings: list[Listing],
    ) -> None:
        if not listings:
            logger.debug("GroupWatcher: no listings for group search #%d", search.id)
            return

        newest = listings[0]

        if search.last_seen_external_id is None:
            logger.info(
                "GroupWatcher: group search #%d — initialised last_seen to %s",
                search.id, newest.external_id,
            )
            repo.update_last_seen(search, newest.external_id)
            return

        if newest.external_id == search.last_seen_external_id:
            logger.debug("GroupWatcher: group search #%d — no new listings", search.id)
            return

        new_listings: list[Listing] = []
        for listing in listings:
            if listing.external_id == search.last_seen_external_id:
                break
            new_listings.append(listing)

        if not new_listings:
            logger.debug(
                "GroupWatcher: group search #%d — could not determine new listings, skipping",
                search.id,
            )
            return

        logger.info(
            "GroupWatcher: group search #%d — %d new listing(s)",
            search.id, len(new_listings),
        )
        repo.update_last_seen(search, newest.external_id)

        route_key = search.route_key if search.route_key in _VALID_ROUTE_KEYS else "other"
        thread_id = _thread_id_for_route_key(route_key, self.config)

        if thread_id is None:
            logger.warning(
                "GroupWatcher: no thread configured for route_key=%r, skipping group search #%d",
                route_key, search.id,
            )
            return

        for raw_listing in new_listings[:5]:
            listing = await self.parser.fetch_and_enrich_listing(raw_listing)
            try:
                await self._send_group_notification(
                    chat_id=self.config.broadcast_chat_id,  # type: ignore[arg-type]
                    thread_id=thread_id,
                    listing=listing,
                )
            except Exception:
                logger.exception(
                    "GroupWatcher: failed to send listing %s to thread %s",
                    listing.external_id,
                    thread_id,
                )

    async def _send_group_notification(
        self,
        chat_id: int,
        thread_id: int,
        listing: Listing,
    ) -> None:
        text = format_listing_message(listing)
        link_btn = InlineKeyboardButton(text="🔗 Skatīt / View", url=listing.url)
        kb = InlineKeyboardMarkup(inline_keyboard=[[link_btn]])

        await send_listing_notification(
            bot=self.bot,
            chat_id=chat_id,
            listing=listing,
            text=text,
            reply_markup=kb,
            thread_id=thread_id,
        )
