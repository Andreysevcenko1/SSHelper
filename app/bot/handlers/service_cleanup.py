"""Auto-delete noisy service messages in groups (joins, leaves, etc.)."""
import logging

from aiogram import F, Router
from aiogram.types import Message

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


@router.message(_SERVICE_FILTER)
async def delete_service_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception as exc:
        logger.warning(
            "Failed to delete service message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            exc,
        )
