import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot import get_main_router
from app.config import load_config
from app.db.session import create_session_factory
from app.services.ss_parser import SSParser
from app.services.watcher import WatcherService

_BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="add", description="Добавить поиск по ссылке SS.lv"),
    BotCommand(command="list", description="Список ваших поисков"),
    BotCommand(command="pause", description="Приостановить поиск: /pause <ID>"),
    BotCommand(command="resume", description="Возобновить поиск: /resume <ID>"),
    BotCommand(command="delete", description="Удалить поиск: /delete <ID>"),
    BotCommand(command="filters", description="Фильтры поиска: /filters <ID>"),
    BotCommand(command="setfilter", description="Установить фильтр: /setfilter <ID> <поле> <значение>"),
    BotCommand(command="delfilter", description="Удалить фильтр: /delfilter <ID> <поле>"),
    BotCommand(command="clearfilters", description="Очистить фильтры: /clearfilters <ID>"),
]


async def run() -> None:
    config = load_config()
    session_factory = create_session_factory(config.database_url)

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Register bot commands in Telegram client menu
    await bot.set_my_commands(_BOT_COMMANDS)

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
