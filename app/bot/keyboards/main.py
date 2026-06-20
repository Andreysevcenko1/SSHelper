from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import MenuCB


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main entry-point menu shown after /start."""
    b = InlineKeyboardBuilder()
    b.button(text="📋 Мои поиски", callback_data=MenuCB(action="searches"))
    b.button(text="➕ Добавить поиск", callback_data=MenuCB(action="add_start"))
    b.adjust(1)
    return b.as_markup()
