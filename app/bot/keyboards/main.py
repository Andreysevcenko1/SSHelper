from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.bot.callbacks import LangCB, MenuCB, SubCB
from app.i18n import get_text

GROUP_URL = "https://t.me/sslvhelper"


def main_menu_kb(lang: str = "lv") -> InlineKeyboardMarkup:
    """Main entry-point menu shown after /start — 4 core buttons only."""
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_add_search", lang), callback_data=MenuCB(action="add_start"))
    b.button(text=get_text("btn_my_searches", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_subscription", lang), callback_data=SubCB(action="show"))
    b.button(text=get_text("btn_language", lang), callback_data=MenuCB(action="lang"))
    b.button(text=get_text("btn_help", lang), callback_data=MenuCB(action="help"))
    b.button(text=get_text("btn_group", lang), url=GROUP_URL)
    b.adjust(1)
    return b.as_markup()


def main_reply_kb(lang: str = "lv") -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown at the bottom of private chat."""
    b = ReplyKeyboardBuilder()
    b.button(text=get_text("btn_my_searches", lang))
    b.button(text=get_text("btn_add_search", lang))
    b.button(text=get_text("btn_subscription", lang))
    b.button(text=get_text("btn_language", lang))
    b.button(text=get_text("btn_help", lang))
    b.adjust(2, 2, 1)
    return b.as_markup(resize_keyboard=True)


def lang_selection_kb(lang: str = "lv") -> InlineKeyboardMarkup:
    """Language picker screen."""
    b = InlineKeyboardBuilder()
    b.button(text="🇱🇻 Latviešu", callback_data=LangCB(lang="lv"))
    b.button(text="🇷🇺 Русский", callback_data=LangCB(lang="ru"))
    b.button(text="🇬🇧 English", callback_data=LangCB(lang="en"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()
