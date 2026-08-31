"""Admin-only commands for managing group searches.

Commands:
  /gadd <route_key> <url> [title]   — add a new group search
  /glist                            — list all group searches
  /gpause <ID>                      — pause a group search
  /gresume <ID>                     — resume a group search
  /gdelete <ID>                     — delete a group search

route_key must be one of: ire_riga, sell_riga, auto_riga, work_riga, flea_market, other
"""

import logging
from urllib.parse import urlparse, urlunparse

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.db.repo import GroupSearchRepository

logger = logging.getLogger(__name__)
router = Router()

_VALID_ROUTE_KEYS = {"ire_riga", "sell_riga", "auto_riga", "work_riga", "flea_market", "other"}
_MAX_TELEGRAM_TEXT = 3900


def _canonical_group_url(url: str, route_key: str) -> str:
    """Normalize known SS.lv category URLs to listing pages with rows.

    SS.lv section roots like ``.../riga/hand_over/`` or ``.../riga/sell/``
    render district categories and contain no listing rows (``tr_*``), so
    watchers get 0 results. For those known flats routes we force ``/all/``.
    """
    raw = (url or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"

    if route_key == "ire_riga" and "/real-estate/flats/riga/hand_over/" in path:
        path = path.replace("/real-estate/flats/riga/hand_over/", "/real-estate/flats/riga/all/hand_over/")
    elif route_key == "sell_riga" and "/real-estate/flats/riga/sell/" in path:
        path = path.replace("/real-estate/flats/riga/sell/", "/real-estate/flats/riga/all/sell/")

    return urlunparse(parsed._replace(path=path))


def _is_admin(message: Message, config: Config) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in config.admin_user_ids


@router.message(Command("gadd"))
async def cmd_gadd(
    message: Message,
    session_factory: sessionmaker[Session],
    config: Config,
) -> None:
    """Add a new group search: /gadd <route_key> <url> [title]"""
    if not _is_admin(message, config):
        return

    parts = (message.text or "").split(maxsplit=3)
    # parts[0] = /gadd, parts[1] = route_key, parts[2] = url, parts[3] = title (optional)
    if len(parts) < 3:
        await message.answer(
            "Usage: /gadd &lt;route_key&gt; &lt;url&gt; [title]\n"
            f"Valid route keys: {', '.join(sorted(_VALID_ROUTE_KEYS))}",
            parse_mode="HTML",
        )
        return

    route_key = parts[1].strip().lower()
    if route_key not in _VALID_ROUTE_KEYS:
        await message.answer(
            f"Invalid route_key <b>{route_key}</b>. "
            f"Must be one of: {', '.join(sorted(_VALID_ROUTE_KEYS))}",
            parse_mode="HTML",
        )
        return

    url = _canonical_group_url(parts[2].strip(), route_key)
    title = parts[3].strip() if len(parts) > 3 else url

    session = session_factory()
    try:
        repo = GroupSearchRepository(session)
        search = repo.add_group_search(title=title, url=url, route_key=route_key)
    finally:
        session.close()

    await message.answer(
        f"✅ Group search <b>#{search.id}</b> added.\n"
        f"Route: <code>{route_key}</code>\n"
        f"URL: {url}",
        parse_mode="HTML",
    )


@router.message(Command("glist"))
async def cmd_glist(
    message: Message,
    session_factory: sessionmaker[Session],
    config: Config,
) -> None:
    """List all group searches."""
    if not _is_admin(message, config):
        return

    session = session_factory()
    try:
        repo = GroupSearchRepository(session)
        searches = repo.get_group_searches()
    finally:
        session.close()

    if not searches:
        await message.answer("No group searches configured.")
        return

    lines = [f"<b>Group searches ({len(searches)}):</b>"]
    for s in searches:
        status = "✅ active" if s.is_active else "⏸ paused"
        lines.append(
            f"#{s.id} [{status}] <code>{s.route_key}</code> — {s.title}\n"
            f"  🔗 {s.effective_url or s.url}"
        )

    # Send in chunks to avoid exceeding 4096 char limit
    # Start fresh chunk with each limit check
    text = "\n\n".join(lines)
    
    if len(text) <= 4096:
        await message.answer(text, parse_mode="HTML")
        return
    
    # Split by items (every 20 items per message)
    items_per_msg = 20
    await message.answer(lines[0], parse_mode="HTML")  # Send header separately
    
    for i in range(1, len(lines), items_per_msg):
        chunk = lines[i:i + items_per_msg]
        await message.answer("\n\n".join(chunk), parse_mode="HTML")


@router.message(Command("gpause"))
async def cmd_gpause(
    message: Message,
    session_factory: sessionmaker[Session],
    config: Config,
) -> None:
    """Pause a group search: /gpause <ID>"""
    if not _is_admin(message, config):
        return

    search_id = _parse_id(message)
    if search_id is None:
        await message.answer("Usage: /gpause &lt;ID&gt;", parse_mode="HTML")
        return

    session = session_factory()
    try:
        repo = GroupSearchRepository(session)
        search = repo.get_group_search_by_id(search_id)
        if search is None:
            await message.answer(f"Group search #{search_id} not found.")
            return
        if not search.is_active:
            await message.answer(f"Group search #{search_id} is already paused.")
            return
        repo.pause_group_search(search)
    finally:
        session.close()

    await message.answer(f"⏸ Group search #{search_id} paused.")


@router.message(Command("gresume"))
async def cmd_gresume(
    message: Message,
    session_factory: sessionmaker[Session],
    config: Config,
) -> None:
    """Resume a group search: /gresume <ID>"""
    if not _is_admin(message, config):
        return

    search_id = _parse_id(message)
    if search_id is None:
        await message.answer("Usage: /gresume &lt;ID&gt;", parse_mode="HTML")
        return

    session = session_factory()
    try:
        repo = GroupSearchRepository(session)
        search = repo.get_group_search_by_id(search_id)
        if search is None:
            await message.answer(f"Group search #{search_id} not found.")
            return
        if search.is_active:
            await message.answer(f"Group search #{search_id} is already active.")
            return
        repo.resume_group_search(search)
    finally:
        session.close()

    await message.answer(f"✅ Group search #{search_id} resumed.")


@router.message(Command("gdelete"))
async def cmd_gdelete(
    message: Message,
    session_factory: sessionmaker[Session],
    config: Config,
) -> None:
    """Delete a group search: /gdelete <ID>"""
    if not _is_admin(message, config):
        return

    search_id = _parse_id(message)
    if search_id is None:
        await message.answer("Usage: /gdelete &lt;ID&gt;", parse_mode="HTML")
        return

    session = session_factory()
    try:
        repo = GroupSearchRepository(session)
        search = repo.get_group_search_by_id(search_id)
        if search is None:
            await message.answer(f"Group search #{search_id} not found.")
            return
        repo.delete_group_search(search)
    finally:
        session.close()

    await message.answer(f"🗑 Group search #{search_id} deleted.")


def _parse_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None


async def _answer_chunks(message: Message, blocks: list[str]) -> None:
    """Send long admin lists in multiple Telegram messages."""
    chunk_parts: list[str] = []
    chunk_len = 0
    for block in blocks:
        add_len = len(block) + (2 if chunk_parts else 0)
        if chunk_parts and chunk_len + add_len > _MAX_TELEGRAM_TEXT:
            await message.answer("\n\n".join(chunk_parts), parse_mode="HTML")
            chunk_parts = [block]
            chunk_len = len(block)
            continue
        chunk_parts.append(block)
        chunk_len += add_len

    if chunk_parts:
        await message.answer("\n\n".join(chunk_parts), parse_mode="HTML")
