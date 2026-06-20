import logging
from aiogram import Bot
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository
from app.services.ss_parser import Listing, SSParser

logger = logging.getLogger(__name__)


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
                    listings = await self.parser.fetch_listings(search.url, limit=5)
                    await self._process_listings(repo=repo, search=search, listings=listings)
                except Exception as exc:
                    logger.warning("Watcher: failed to process search #%d — %s", search.id, exc)
                    continue
        finally:
            session.close()

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

        logger.info("Watcher: search #%d — new listing %s", search.id, newest.external_id)
        repo.update_last_seen(search, newest.external_id)

        lines = [
            f"🔔 Новое объявление (поиск #{search.id}):",
            f"Название: {newest.title}",
        ]
        if newest.price:
            lines.append(f"Цена: {newest.price}")
        if newest.city:
            lines.append(f"Город: {newest.city}")
        lines.append(f"🔗 {newest.url}")

        await self.bot.send_message(
            chat_id=search.user_id,
            text="\n".join(lines),
        )
