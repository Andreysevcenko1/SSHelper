from aiogram import Bot
from sqlalchemy.orm import Session, sessionmaker

from app.db.repo import SearchRepository
from app.services.ss_parser import Listing, SSParser


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

            for search in searches:
                try:
                    listings = await self.parser.fetch_listings(search.url, limit=5)
                    await self._process_listings(repo=repo, search=search, listings=listings)
                except Exception:
                    continue
        finally:
            session.close()

    async def _process_listings(self, repo: SearchRepository, search, listings: list[Listing]) -> None:
        if not listings:
            return

        newest = listings[0]

        if search.last_seen_external_id is None:
            repo.update_last_seen(search, newest.external_id)
            return

        if newest.external_id == search.last_seen_external_id:
            return

        repo.update_last_seen(search, newest.external_id)

        price_text = f"\\nЦена: {newest.price}" if newest.price else ""
        await self.bot.send_message(
            chat_id=search.user_id,
            text=(
                f"Найдено новое объявление по поиску #{search.id}:\\n"
                f"{newest.title}{price_text}\\n"
                f"{newest.url}"
            ),
        )
