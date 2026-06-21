import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository, UserSettingsRepository
from app.i18n import get_text, resolve_lang
from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)

_MAX_PHOTOS_PER_NOTIFICATION = 3


class WatcherService:
    def __init__(self, session_factory: sessionmaker[Session], parser: SSParser, bot: Bot) -> None:
        self.session_factory = session_factory
        self.parser = parser
        self.bot = bot

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
                except Exception as exc:
                    logger.warning("Watcher: failed to process search #%d — %s", search.id, exc)
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
        for listing in new_listings[:5]:
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
            except Exception as exc:
                logger.error(
                    "Watcher: unexpected error sending notification for search #%d — %s",
                    search.id, exc,
                )

    async def _send_notification(
        self,
        chat_id: int,
        search_id: int,
        listing: Listing,
        lang: str,
    ) -> None:
        """Send a notification for a single new listing, with photo if available."""
        lines = [
            get_text("new_listing", lang),
            get_text("notification_search_label", lang, sid=search_id),
            "",
            get_text("listing_title", lang, title=listing.title),
        ]
        if listing.price:
            lines.append(get_text("listing_price", lang, price=listing.price))
        if listing.city:
            lines.append(get_text("listing_city", lang, city=listing.city))

        text = "\n".join(lines)

        # Build inline keyboard with link button
        link_btn = InlineKeyboardButton(
            text=get_text("listing_link", lang),
            url=listing.url,
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[link_btn]])

        valid_photos = [
            url for url in listing.photo_urls[:_MAX_PHOTOS_PER_NOTIFICATION]
            if url and url.startswith("http")
        ]

        if len(valid_photos) > 1:
            # Send media group (up to 3 photos)
            media = []
            for i, photo_url in enumerate(valid_photos):
                if i == 0:
                    media.append(InputMediaPhoto(media=photo_url, caption=text, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=photo_url))
            try:
                await self.bot.send_media_group(chat_id=chat_id, media=media)
                # Send the link button as a follow-up text (media groups don't support reply_markup)
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔗 {listing.url}",
                    reply_markup=kb,
                )
                return
            except Exception as exc:
                logger.warning("Watcher: send_media_group failed (%s), falling back to text", exc)

        elif len(valid_photos) == 1:
            try:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=valid_photos[0],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            except Exception as exc:
                logger.warning("Watcher: send_photo failed (%s), falling back to text", exc)

        # Fallback: plain text message
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"{text}\n\n🔗 {listing.url}",
            parse_mode="HTML",
            reply_markup=kb,
        )
