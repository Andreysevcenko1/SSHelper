"""Remove Telegram "Deleted Account" users from the broadcast group.

Requires TG_API_ID and TG_API_HASH from https://my.telegram.org/apps.
The bot must be an admin in the target group with permission to ban users.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from telethon import TelegramClient
    from telethon.errors import ChatAdminRequiredError, FloodWaitError
except ModuleNotFoundError as exc:
    if exc.name == "telethon":
        raise SystemExit(
            "Telethon is not installed. Run: pip install -r requirements.txt"
        ) from exc
    raise

from app.config import load_config


def _get_api_id() -> int:
    raw = os.getenv("TG_API_ID", "").strip() or input("App api_id: ").strip()
    return int(raw)


def _get_api_hash() -> str:
    return os.getenv("TG_API_HASH", "").strip() or getpass.getpass("App api_hash: ").strip()


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove Telegram Deleted Account users from BROADCAST_CHAT_ID."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print deleted users, do not remove them.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between removals to avoid Telegram flood limits.",
    )
    args = parser.parse_args()

    cfg = load_config()
    if cfg.broadcast_chat_id is None:
        raise RuntimeError("BROADCAST_CHAT_ID is not set in .env")

    client = TelegramClient("cleanup_deleted_users", _get_api_id(), _get_api_hash())
    await client.start(bot_token=cfg.telegram_bot_token)

    checked = 0
    deleted_found = 0
    removed = 0
    failed = 0

    print(f"Checking group: {cfg.broadcast_chat_id}")
    if args.dry_run:
        print("DRY RUN: deleted accounts will only be listed, not removed.")

    try:
        async for user in client.iter_participants(cfg.broadcast_chat_id):
            checked += 1
            if not getattr(user, "deleted", False):
                continue

            deleted_found += 1
            if args.dry_run:
                print(f"Found Deleted Account id={user.id}")
                continue

            try:
                await client.kick_participant(cfg.broadcast_chat_id, user)
                removed += 1
                print(f"Removed Deleted Account id={user.id}")
                await asyncio.sleep(args.delay)
            except FloodWaitError as exc:
                print(f"Flood wait {exc.seconds}s, sleeping...")
                await asyncio.sleep(exc.seconds + 2)
                try:
                    await client.kick_participant(cfg.broadcast_chat_id, user)
                    removed += 1
                    print(f"Removed after wait id={user.id}")
                    await asyncio.sleep(args.delay)
                except Exception as retry_exc:
                    failed += 1
                    print(f"Failed after wait id={user.id}: {retry_exc}")
            except Exception as exc:
                failed += 1
                print(f"Failed id={user.id}: {exc}")
    except ChatAdminRequiredError:
        raise RuntimeError(
            "Bot is not an admin or lacks Ban users permission in the group."
        ) from None
    finally:
        await client.disconnect()

    print("\nDONE")
    print(f"Checked: {checked}")
    print(f"Deleted accounts found: {deleted_found}")
    print(f"Removed: {removed}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(_main())
