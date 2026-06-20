from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.main import main_menu_kb
from app.bot.utils import try_delete_message

router = Router()

_WELCOME = (
    "👋 Привет! Я <b>SSHelper</b> — бот для мониторинга объявлений на SS.lv.\n\n"
    "<b>Доступные команды:</b>\n"
    "/add &lt;ссылка&gt; — добавить поиск\n"
    "/list — список ваших поисков\n"
    "/pause &lt;ID&gt; — приостановить поиск\n"
    "/resume &lt;ID&gt; — возобновить поиск\n"
    "/delete &lt;ID&gt; — удалить поиск\n"
    "/filters &lt;ID&gt; — фильтры поиска\n"
    "/setfilter &lt;ID&gt; &lt;поле&gt; &lt;значение&gt; — установить фильтр\n"
    "/delfilter &lt;ID&gt; &lt;поле&gt; — удалить фильтр\n"
    "/clearfilters &lt;ID&gt; — очистить все фильтры\n\n"
    "Или используйте кнопки меню ниже:"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await try_delete_message(message)
    await message.answer(_WELCOME, reply_markup=main_menu_kb())

