"""Auto-delete noisy service messages in groups (joins, leaves, etc.)."""
import logging

from aiogram import F, Router
from aiogram.types import Message

from app.config import Config

logger = logging.getLogger(__name__)

router = Router(name="service_cleanup")

_SERVICE_FILTER = (
    F.new_chat_members
    | F.left_chat_member
    | F.new_chat_title
    | F.new_chat_photo
    | F.delete_chat_photo
    | F.pinned_message
    | F.video_chat_started
    | F.video_chat_ended
    | F.video_chat_participants_invited
)


async def _notify_admins_about_members(message: Message, config: Config) -> None:
    """DM admins when members join or leave the group."""
    lines: list[str] = []
    if message.new_chat_members:
        for user in message.new_chat_members:
            if user.is_bot:
                continue
            name = user.full_name
            username = f" (@{user.username})" if user.username else ""
            lines.append(
                f"➕ Новый участник: <b>{name}</b>{username}\n"
                f"   ID: <code>{user.id}</code>\n"
                f"   Группа: {message.chat.title}"
            )
    elif message.left_chat_member and not message.left_chat_member.is_bot:
        user = message.left_chat_member
        name = user.full_name
        username = f" (@{user.username})" if user.username else ""
        lines.append(
            f"➖ Участник вышел: <b>{name}</b>{username}\n"
            f"   ID: <code>{user.id}</code>\n"
            f"   Группа: {message.chat.title}"
        )

    if not lines:
        return

    text = "\n\n".join(lines)
    for admin_id in config.admin_user_ids:
        try:
            await message.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Failed to notify admin %s: %s", admin_id, exc)


@router.message(_SERVICE_FILTER)
async def delete_service_message(message: Message, config: Config) -> None:
    try:
        await _notify_admins_about_members(message, config)
    except Exception as exc:
        logger.warning("Failed to send member notification: %s", exc)

    try:
        await message.delete()
    except Exception as exc:
        logger.warning(
            "Failed to delete service message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            exc,
        )
