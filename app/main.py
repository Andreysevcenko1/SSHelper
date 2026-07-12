import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.bot import get_main_router
from app.config import load_config
from app.db.repo import GroupSearchRepository, SearchRepository
from app.db.session import create_session_factory
from app.services.group_watcher import GroupWatcherService
from app.services.ss_parser import SSParser
from app.services.watcher import WatcherService

_BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню / Main menu / Galvenā izvēlne"),
    BotCommand(command="add", description="Добавить поиск / Add search"),
    BotCommand(command="list", description="Список поисков / List searches"),
    BotCommand(command="lang", description="Язык / Language / Valoda"),
    BotCommand(command="pause", description="Приостановить поиск: /pause <ID>"),
    BotCommand(command="resume", description="Возобновить поиск: /resume <ID>"),
    BotCommand(command="delete", description="Удалить поиск: /delete <ID>"),
    BotCommand(command="filters", description="Фильтры поиска: /filters <ID>"),
    BotCommand(command="setfilter", description="Установить фильтр: /setfilter <ID> <поле> <значение>"),
    BotCommand(command="delfilter", description="Удалить фильтр: /delfilter <ID> <поле>"),
    BotCommand(command="clearfilters", description="Очистить фильтры: /clearfilters <ID>"),
]

# Admin-only commands: shown in the menu only for ADMIN_USER_IDS chats.
_ADMIN_COMMANDS = _BOT_COMMANDS + [
    BotCommand(command="gadd", description="[Admin] Добавить групповой поиск: /gadd <route> <url> [title]"),
    BotCommand(command="glist", description="[Admin] Список групповых поисков"),
    BotCommand(command="gpause", description="[Admin] Приостановить: /gpause <ID>"),
    BotCommand(command="gresume", description="[Admin] Возобновить: /gresume <ID>"),
    BotCommand(command="gdelete", description="[Admin] Удалить: /gdelete <ID>"),
    BotCommand(command="stars", description="[Admin] Баланс/транзакции Stars"),
]

logger = logging.getLogger(__name__)


def _db_hygiene_job(session_factory: sessionmaker[Session]) -> None:
    """Periodic DB hygiene: prune dead searches and vacuum."""
    session = session_factory()
    try:
        repo = SearchRepository(session)
        pruned = repo.prune_old_inactive_searches(older_than_days=90)
        if pruned:
            logger.info("DB hygiene: pruned %d old inactive search(es)", pruned)
        repo.vacuum()
    except Exception as exc:
        logger.warning("DB hygiene job failed: %s", exc)
    finally:
        session.close()


async def run() -> None:
    config = load_config()
    session_factory = create_session_factory(config.database_url)

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Register bot commands in Telegram client menu
    await bot.set_my_commands(_BOT_COMMANDS)
    # Admins additionally see the [Admin] commands in their private chat menu.
    for admin_id in config.admin_user_ids:
        try:
            await bot.set_my_commands(
                _ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception as exc:
            logger.warning("Could not set admin commands for %s: %s", admin_id, exc)

    dp = Dispatcher()
    dp.include_router(get_main_router())

    parser = SSParser()
    from app.services.fetch_coordinator import FetchCoordinator
    coordinator = FetchCoordinator(parser)
    watcher = WatcherService(
        session_factory=session_factory, parser=parser, bot=bot, config=config,
        coordinator=coordinator,
    )

    # Group watcher — independent pipeline, only runs when broadcast is configured
    group_watcher: GroupWatcherService | None = None
    if config.broadcast_enabled:
        group_watcher = GroupWatcherService(
            session_factory=session_factory,
            parser=parser,
            bot=bot,
            config=config,
            coordinator=coordinator,
        )
        session = session_factory()
        try:
            active_count = len(GroupSearchRepository(session).get_active_group_searches())
        finally:
            session.close()
        logger.info(
            "Group watcher enabled: %d active group search(es), interval=%ds",
            active_count,
            config.group_poll_interval_seconds,
        )
    else:
        logger.info("Group watcher disabled (BROADCAST_ENABLED is false)")

    logger.info(
        "Personal watcher enabled: interval=%ds",
        config.poll_interval_seconds,
    )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(watcher.check_all, trigger="interval", seconds=config.poll_interval_seconds)
    if group_watcher is not None:
        scheduler.add_job(
            group_watcher.check_all,
            trigger="interval",
            seconds=config.group_poll_interval_seconds,
        )
    # DB hygiene runs once a day
    scheduler.add_job(
        _db_hygiene_job,
        trigger="interval",
        hours=24,
        args=[session_factory],
    )
    scheduler.start()

    try:
        await dp.start_polling(bot, session_factory=session_factory, config=config)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
