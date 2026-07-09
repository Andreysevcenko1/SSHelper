import logging
import unicodedata
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.db.repo import BroadcastRepository, SearchRepository, UserSettingsRepository
from app.i18n import get_text, resolve_lang
from app.services.formatter import format_listing_message
from app.services.filters import filters_from_json
from app.services.listing_filter import listing_matches_filters
from app.filters.profiles import detect_profile
from app.services.notifier import send_listing_notification
from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Routing helpers
# ──────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase and strip diacritics (ā→a, ī→i, ū→u, etc.)."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_RENT_KEYWORDS = {
    "ire", "rent", "dzivoklu ire", "dzivoklis ire", "nomai", "iznoma",
    "hand_over",  # SS.lv URL segment for rental
}
_SALE_KEYWORDS = {
    "pardosana", "sale", "dzivoklu pardosana", "pirkt",
    "sell",  # SS.lv URL segment for sale
}
_AUTO_KEYWORDS = {
    "auto", "cars", "transport", "masinas", "automobili",
}
_RIGA_KEYWORDS = {"riga"}


def _is_riga(city: str | None, url: str) -> bool:
    """Return True if the listing appears to be in Rīga."""
    sources = []
    if city:
        sources.append(_normalize(city))
    sources.append(_normalize(url))
    return any(kw in src for src in sources for kw in _RIGA_KEYWORDS)


def _detect_topic(search_url: str, listing: "Listing", config: Config) -> int:
    """Return the Telegram message_thread_id for *listing* based on routing rules.

    Routing priority:
      1. Rīga + apartment rent  → THREAD_IRE_RIGA
      2. Rīga + apartment sale  → THREAD_SELL_RIGA
      3. Rīga + auto            → THREAD_AUTO_RIGA
      4. everything else        → THREAD_OTHER_CITIES
    """
    url_norm = _normalize(search_url)
    title_norm = _normalize(listing.title or "")
    combined = f"{url_norm} {title_norm}"

    is_riga = _is_riga(listing.city, search_url)

    is_rent = any(kw in combined for kw in _RENT_KEYWORDS)
    is_sale = any(kw in combined for kw in _SALE_KEYWORDS)
    is_auto = any(kw in combined for kw in _AUTO_KEYWORDS)

    if is_riga and is_rent:
        thread_id = config.thread_ire_riga
        reason = "Rīga + rent"
    elif is_riga and is_sale:
        thread_id = config.thread_sell_riga
        reason = "Rīga + sale"
    elif is_riga and is_auto:
        thread_id = config.thread_auto_riga
        reason = "Rīga + auto"
    else:
        thread_id = config.thread_other_cities
        reason = "other"

    logger.debug(
        "Broadcast routing: listing %s → thread %s (%s)",
        listing.external_id, thread_id, reason,
    )
    # thread_id is guaranteed non-None when broadcast_enabled (validated in load_config)
    return thread_id  # type: ignore[return-value]


class WatcherService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        parser: SSParser,
        bot: Bot,
        config: Config | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.parser = parser
        self.bot = bot
        self.config = config

        if config and config.broadcast_enabled:
            logger.info(
                "Broadcast enabled: chat_id=%s threads=(ire_riga=%s, sell_riga=%s, "
                "auto_riga=%s, other=%s)",
                config.broadcast_chat_id,
                config.thread_ire_riga,
                config.thread_sell_riga,
                config.thread_auto_riga,
                config.thread_other_cities,
            )
        else:
            logger.info("Broadcast disabled — DM-only mode")

    async def check_all(self) -> None:
        session = self.session_factory()
        try:
            repo = SearchRepository(session)
            searches = repo.get_active_searches()
            logger.info("Watcher: checking %d active search(es)", len(searches))

            for search in searches:
                try:
                    fetch_url = search.effective_url or search.url
                    listings = await self.parser.fetch_listings(fetch_url, limit=10)
                    await self._process_listings(repo=repo, search=search, listings=listings)
                except Exception:
                    logger.exception("Watcher: failed to process search #%d", search.id)
                    continue
        finally:
            session.close()

    def _resolve_user_lang(self, user_id: int) -> str:
        """Fetch user's preferred language from DB."""
        session = self.session_factory()
        try:
            db_lang = UserSettingsRepository(session).get_lang(user_id)
        finally:
            session.close()
        return resolve_lang(None, db_lang)

    async def _process_listings(self, repo: SearchRepository, search, listings: list[Listing]) -> None:
        if not listings:
            logger.debug("Watcher: no listings found for search #%d", search.id)
            return

        newest = listings[0]

        if search.last_seen_external_id is None:
            logger.info("Watcher: search #%d — initialised last_seen to %s", search.id, newest.external_id)
            repo.update_last_seen(search, newest.external_id)
            return

        if newest.external_id == search.last_seen_external_id:
            logger.debug("Watcher: search #%d — no new listings", search.id)
            return

        # Collect all new listings (everything before the last_seen_external_id)
        new_listings: list[Listing] = []
        for listing in listings:
            if listing.external_id == search.last_seen_external_id:
                break
            new_listings.append(listing)

        if not new_listings:
            logger.debug("Watcher: search #%d — could not determine new listings, skipping", search.id)
            return

        logger.info("Watcher: search #%d — %d new listing(s)", search.id, len(new_listings))
        repo.update_last_seen(search, newest.external_id)

        lang = self._resolve_user_lang(search.user_id)

        # Send notifications for new listings (newest first, up to 5)
        for raw_listing in new_listings[:5]:
            listing = await self.parser.fetch_and_enrich_listing(raw_listing)
            matches, fail_reason = listing_matches_filters(
                listing,
                filters_from_json(search.filters_json),
                search.category_profile or detect_profile(search.effective_url or search.url or ""),
            )
            if not matches:
                logger.info(
                    "Watcher: search #%d — listing %s filtered out locally: %s",
                    search.id, listing.external_id, fail_reason,
                )
            if matches:
                try:
                    await self._send_notification(
                        chat_id=search.user_id,
                        search_id=search.id,
                        listing=listing,
                        lang=lang,
                    )
                except (TelegramBadRequest, TelegramForbiddenError) as exc:
                    logger.warning(
                        "Watcher: failed to send notification for search #%d listing %s — %s",
                        search.id, listing.external_id, exc,
                    )
                except Exception:
                    logger.exception(
                        "Watcher: unexpected error sending notification for search #%d",
                        search.id,
                    )

            # Group broadcast (feature-flagged, deduped per external_id)
            if self.config and self.config.broadcast_enabled:
                await self._maybe_broadcast(search_url=search.effective_url or search.url, listing=listing)

    async def _maybe_broadcast(self, search_url: str, listing: Listing) -> None:
        """Send *listing* to the group forum topic if not already sent."""
        assert self.config is not None  # guaranteed by caller

        session = self.session_factory()
        try:
            bc_repo = BroadcastRepository(session)
            if bc_repo.already_sent(listing.external_id):
                logger.debug(
                    "Broadcast dedupe: skipping %s (already sent)", listing.external_id
                )
                return

            thread_id = _detect_topic(search_url, listing, self.config)

            try:
                await self._send_group_notification(
                    chat_id=self.config.broadcast_chat_id,  # type: ignore[arg-type]
                    thread_id=thread_id,
                    listing=listing,
                )
            except Exception:
                logger.exception(
                    "Broadcast: failed to send listing %s to thread %s",
                    listing.external_id,
                    thread_id,
                )
                return

            # Only mark as sent after a successful delivery
            sent = bc_repo.mark_sent(listing.external_id)
            if not sent:
                logger.debug("Broadcast dedupe: race-condition skip for %s", listing.external_id)
        finally:
            session.close()

    async def _send_notification(
        self,
        chat_id: int,
        search_id: int,
        listing: Listing,
        lang: str,
    ) -> None:
        """Send a notification for a single new listing with HD photo if available."""
        header = "\n".join([
            get_text("new_listing", lang),
            get_text("notification_search_label", lang, sid=search_id),
            "",
        ])
        body = format_listing_message(listing)
        text = header + body

        link_btn = InlineKeyboardButton(
            text=get_text("listing_link", lang),
            url=listing.url,
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[link_btn]])

        await send_listing_notification(bot=self.bot, chat_id=chat_id, listing=listing, text=text, reply_markup=kb)

    async def _send_group_notification(
        self,
        chat_id: int,
        thread_id: int,
        listing: Listing,
    ) -> None:
        """Send a listing to a forum topic using the unified formatter."""
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
