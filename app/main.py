import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot import get_main_router
from app.config import load_config
from app.db.session import create_session_factory
from app.services.ss_parser import SSParser
from app.services.watcher import WatcherService


async def run() -> None:
    config = load_config()
    session_factory = create_session_factory(config.database_url)

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(get_main_router())

    parser = SSParser()
    watcher = WatcherService(session_factory=session_factory, parser=parser, bot=bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(watcher.check_all, trigger="interval", seconds=config.poll_interval_seconds)
    scheduler.start()

    try:
        await dp.start_polling(bot, session_factory=session_factory)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
