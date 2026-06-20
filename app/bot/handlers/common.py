from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я <b>SSHelper</b> — бот для мониторинга объявлений на SS.lv.\n\n"
        "<b>Команды:</b>\n"
        "/add &lt;ссылка&gt; — добавить поиск\n"
        "/list — показать все ваши поиски\n"
        "/pause &lt;ID&gt; — приостановить поиск\n"
        "/resume &lt;ID&gt; — возобновить поиск\n"
        "/delete &lt;ID&gt; — удалить поиск\n\n"
        "<b>Пример:</b>\n"
        "<code>/add https://www.ss.lv/lv/transport/cars/</code>"
    )
