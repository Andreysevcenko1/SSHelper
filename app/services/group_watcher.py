"""Group watcher service.

Polls GroupSearch records independently of personal user searches and posts
new listings directly to the configured forum topics (message_thread_id).
No user_id involvement at any point.
"""

import asyncio
import html
import logging
import re

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.db.models import GroupSearch
from app.db.repo import GroupSearchRepository
from app.services.fetch_coordinator import FetchCoordinator
from app.services.facebook_publisher import publish_to_facebook_page
from app.services.formatter import format_listing_message, select_image_url
from app.services.listing_filter import is_buy_request
from app.services.notifier import send_listing_notification
from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)

_VALID_ROUTE_KEYS = {"ire_riga", "sell_riga", "auto_riga", "work_riga", "flea_market", "other"}

_HTML_TAG_RE = re.compile(r"<[^>]+>")

_FACEBOOK_ROUTE_HEADERS = {
    "ire_riga": "🏠 DZĪVOKĻI / ĪRE RĪGĀ\n#SSlv #Riga #Dzivokli #Ire",
    "sell_riga": "🏢 DZĪVOKĻI / PĀRDOŠANA RĪGĀ\n#SSlv #Riga #Dzivokli #Pardosana",
    "auto_riga": "🚗 AUTO RĪGĀ\n#SSlv #Riga #Auto",
    "work_riga": "💼 DARBS RĪGĀ\n#SSlv #Riga #Darbs",
    "flea_market": "📦 MANTAS / TIRGUS\n#SSlv #Riga #Mantas",
    "other": "📍 CITI SS.LV SLUDINĀJUMI\n#SSlv #Riga #Sludinajumi",
}

def _to_facebook_text(html_text: str, listing_url: str, route_key: str | None = None) -> str:
    """Strip HTML markup from a Telegram-formatted message for Facebook Feed/Photo posts.

    Facebook's Graph API does not render HTML — it only accepts plain text.
    The listing URL is preserved on its own line so Facebook can still
    auto-linkify it. A route header is added when available to emulate the
    Telegram forum-topic structure in Facebook's flat Page feed.
    """
    plain = _HTML_TAG_RE.sub("", html_text)
    plain = html.unescape(plain)
    if listing_url not in plain:
        plain = f"{plain}\n{listing_url}"
    header = _FACEBOOK_ROUTE_HEADERS.get(route_key or "")
    if header:
        plain = f"{header}\n\n{plain}"
    return plain.strip()


def _thread_id_for_route_key(route_key: str, config: Config) -> int | None:
    """Map a route_key string to the corresponding Telegram thread id.

    Returns None when the relevant thread is not configured.
    Falls back to THREAD_OTHER_CITIES for unknown/invalid keys.
    """
    mapping = {
        "ire_riga": config.thread_ire_riga,
        "sell_riga": config.thread_sell_riga,
        "auto_riga": config.thread_auto_riga,
        "work_riga": config.thread_work_riga,
        "flea_market": config.thread_flea_market,
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
        coordinator: FetchCoordinator | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.parser = parser
        self.bot = bot
        self.config = config
        self.coordinator = coordinator or FetchCoordinator(parser)

    async def check_all(self) -> None:
        session = self.session_factory()
        try:
            repo = GroupSearchRepository(session)
            searches = repo.get_active_group_searches()
            logger.info("GroupWatcher: checking %d active group search(es)", len(searches))

            self.coordinator.prune()

            async def _check_one(search) -> None:
                try:
                    fetch_url = search.effective_url or search.url
                    listings = await self.coordinator.fetch_listings(fetch_url, limit=10)
                    logger.info(
                        "GroupWatcher: group search #%d fetched %d listing(s) from %s",
                        search.id,
                        len(listings),
                        fetch_url,
                    )
                    await self._process_listings(repo=repo, search=search, listings=listings)
                except Exception:
                    logger.exception(
                        "GroupWatcher: failed to process group search #%d",
                        search.id,
                    )

            await asyncio.gather(*(_check_one(s) for s in searches))
        finally:
            session.close()

    async def _process_listings(
        self,
        repo: GroupSearchRepository,
        search: GroupSearch,
        listings: list[Listing],
    ) -> None:
        if not listings:
            logger.warning("GroupWatcher: no listings for group search #%d", search.id)
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

        # "Citi pilsētu sludinājumi" topic is flats-only: never post cars there.
        fetch_url = str(
            getattr(search, "effective_url", None) or getattr(search, "url", "") or ""
        ).lower()
        if route_key == "other" and ("/transport/" in fetch_url or "/cars/" in fetch_url):
            logger.info(
                "GroupWatcher: group search #%d is auto but routed to other-cities topic — skipping",
                search.id,
            )
            return

        thread_id = _thread_id_for_route_key(route_key, self.config)

        if thread_id is None:
            logger.warning(
                "GroupWatcher: no thread configured for route_key=%r, skipping group search #%d",
                route_key, search.id,
            )
            return

        for raw_listing in new_listings[:5]:
            listing = await self.coordinator.enrich_listing(raw_listing)
            if is_buy_request(listing):
                logger.info(
                    "GroupWatcher: listing %s skipped (buy-request ad): %r",
                    listing.external_id, listing.title,
                )
                continue
            try:
                await self._send_group_notification(
                    chat_id=self.config.broadcast_chat_id,  # type: ignore[arg-type]
                    thread_id=thread_id,
                    listing=listing,
                    route_key=route_key,
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
        route_key: str | None = None,
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

        if self.config.facebook_enabled:
            fb_text = _to_facebook_text(text, listing.url, route_key=route_key)
            image_url = select_image_url(listing)
            await publish_to_facebook_page(
                config=self.config,
                text=fb_text,
                image_url=image_url,
                listing_id=listing.external_id,
            )
