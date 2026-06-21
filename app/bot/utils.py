import logging
from typing import Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def delete_message_safe(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Delete a message silently.

    Returns True if the message was deleted, False if it could not be deleted
    (e.g. bot lacks permissions, message is too old, already deleted).
    Never raises.
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug(
            "delete_message_safe: cannot delete msg %d in chat %d — %s",
            message_id,
            chat_id,
            exc,
        )
        return False


async def try_delete_message(message: Message) -> bool:
    """Try to delete a Message object silently.

    Returns True on success, False on failure (never raises).
    """
    if message.bot is None:
        return False
    return await delete_message_safe(message.bot, message.chat.id, message.message_id)


async def cleanup_user_and_service_messages(
    bot: Bot,
    chat_id: int,
    message_ids: Sequence[int],
) -> int:
    """Silently delete a list of messages (user replies and bot service messages).

    Returns the count of successfully deleted messages.
    Never raises.
    """
    deleted = 0
    for msg_id in message_ids:
        if await delete_message_safe(bot, chat_id, msg_id):
            deleted += 1
    return deleted
