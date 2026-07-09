from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import LangCB, MenuCB, SubCB
from app.i18n import get_text


def main_menu_kb(lang: str = "lv") -> InlineKeyboardMarkup:
    """Main entry-point menu shown after /start — 4 core buttons only."""
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_add_search", lang), callback_data=MenuCB(action="add_start"))
    b.button(text=get_text("btn_my_searches", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_subscription", lang), callback_data=SubCB(action="show"))
    b.button(text=get_text("btn_language", lang), callback_data=MenuCB(action="lang"))
    b.button(text=get_text("btn_help", lang), callback_data=MenuCB(action="help"))
    b.adjust(1)
    return b.as_markup()


def lang_selection_kb(lang: str = "lv") -> InlineKeyboardMarkup:
    """Language picker screen."""
    b = InlineKeyboardBuilder()
    b.button(text="🇱🇻 Latviešu", callback_data=LangCB(lang="lv"))
    b.button(text="🇷🇺 Русский", callback_data=LangCB(lang="ru"))
    b.button(text="🇬🇧 English", callback_data=LangCB(lang="en"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()
