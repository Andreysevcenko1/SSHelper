from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import MenuCB, SearchCB
from app.i18n import get_text

CATEGORY_LABELS: dict[str, str] = {
    "Транспорт": "🚗 Транспорт",
    "Недвижимость": "🏠 Недвижимость",
    "Животные": "🐾 Животные",
    "Электроника": "💻 Электроника",
    "Услуги": "🔧 Услуги",
    "Прочее": "📦 Прочее",
    "Одежда": "👗 Одежда",
    "Сад и огород": "🌱 Сад и огород",
    "Еда": "🍎 Еда",
    "Спорт": "⚽ Спорт",
    "Бизнес": "💼 Бизнес",
    "Коллекционирование": "🏺 Коллекционирование",
    "Дом и быт": "🏡 Дом и быт",
    "SS.lv": "📋 SS.lv",
}

CATEGORY_ICONS: dict[str, str] = {
    "Транспорт": "🚗",
    "Недвижимость": "🏠",
    "Животные": "🐾",
    "Электроника": "💻",
    "Услуги": "🔧",
    "Прочее": "📦",
    "Одежда": "👗",
    "Сад и огород": "🌱",
    "Еда": "🍎",
    "Спорт": "⚽",
    "Бизнес": "💼",
    "Коллекционирование": "🏺",
    "Дом и быт": "🏡",
    "SS.lv": "📋",
}


def searches_list_kb(searches: list, lang: str = "lv") -> InlineKeyboardMarkup:
    """List of user searches with tap-to-view action."""
    b = InlineKeyboardBuilder()
    for s in searches:
        icon = CATEGORY_ICONS.get(s.title, "📋")
        state_icon = "▶️" if s.is_active else "⏸"
        b.button(
            text=f"{state_icon} {icon} #{s.id} — {s.title}",
            callback_data=SearchCB(action="view", sid=s.id),
        )
    b.button(text=get_text("btn_add_search", lang), callback_data=MenuCB(action="add_start"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def search_actions_kb(search_id: int, is_active: bool, lang: str = "lv") -> InlineKeyboardMarkup:
    """Actions for a specific search: pause/resume, filters, delete, back."""
    b = InlineKeyboardBuilder()
    if is_active:
        b.button(text=get_text("btn_pause", lang), callback_data=SearchCB(action="pause", sid=search_id))
    else:
        b.button(text=get_text("btn_resume", lang), callback_data=SearchCB(action="resume", sid=search_id))
    b.button(text=get_text("btn_filters", lang), callback_data=SearchCB(action="filters", sid=search_id))
    b.button(text=get_text("btn_delete", lang), callback_data=SearchCB(action="delete", sid=search_id))
    b.button(text=get_text("btn_my_searches_short", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(2, 1, 2)
    return b.as_markup()


def after_add_kb(search_id: int, lang: str = "lv") -> InlineKeyboardMarkup:
    """Shown after a search is successfully added."""
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_open_filters", lang), callback_data=SearchCB(action="filters", sid=search_id))
    b.button(text=get_text("btn_my_searches_short", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_add_more", lang), callback_data=MenuCB(action="add_start"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1, 2, 1)
    return b.as_markup()


def after_action_kb(lang: str = "lv") -> InlineKeyboardMarkup:
    """Shown after pause/resume/delete."""
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_my_searches_short", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(2)
    return b.as_markup()


def error_kb(back_search_id: int = 0, lang: str = "lv") -> InlineKeyboardMarkup:
    """Shown after an error; offers Back (to search or list) and Menu."""
    b = InlineKeyboardBuilder()
    if back_search_id:
        b.button(
            text=get_text("btn_back_to_search", lang),
            callback_data=SearchCB(action="view", sid=back_search_id),
        )
    b.button(text=get_text("btn_my_searches_short", lang), callback_data=MenuCB(action="searches"))
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()
