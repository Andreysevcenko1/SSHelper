from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я SSHelper.\\n"
        "Добавь поиск командой: /add <ссылка_на_поиск_ss.lv>"
    )
