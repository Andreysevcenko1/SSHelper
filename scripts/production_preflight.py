"""Validate production configuration, imports, database access, and Telegram auth."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        f"Python 3.11+ is required, found {sys.version_info.major}.{sys.version_info.minor}"
    )

from aiogram import Bot
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_config
import app.db.models  # noqa: F401 - register SQLAlchemy models before create_all
from app.db.session import create_session_factory


def _check_database(database_url: str) -> None:
    session_factory = create_session_factory(database_url)
    session = session_factory()
    try:
        session.execute(text("SELECT 1")).scalar_one()
    finally:
        session.close()


async def _check_telegram(token: str) -> str:
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        return f"@{me.username}" if me.username else str(me.id)
    finally:
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Also verify the bot token against the Telegram API.",
    )
    args = parser.parse_args()

    config = load_config()
    _check_database(config.database_url)

    print("config: ok")
    print("database: ok")
    print(f"admins: {len(config.admin_user_ids)}")
    print(f"broadcast: {'enabled' if config.broadcast_enabled else 'disabled'}")
    if args.telegram:
        identity = asyncio.run(_check_telegram(config.telegram_bot_token))
        print(f"telegram: ok ({identity})")


if __name__ == "__main__":
    main()
