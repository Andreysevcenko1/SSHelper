from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import MenuCB, SearchCB

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


def searches_list_kb(searches: list) -> InlineKeyboardMarkup:
    """List of user searches with tap-to-view action."""
    b = InlineKeyboardBuilder()
    for s in searches:
        icon = CATEGORY_ICONS.get(s.title, "📋")
        state_icon = "▶️" if s.is_active else "⏸"
        b.button(
            text=f"{state_icon} {icon} #{s.id} — {s.title}",
            callback_data=SearchCB(action="view", sid=s.id),
        )
    b.button(text="➕ Добавить поиск", callback_data=MenuCB(action="add_start"))
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def search_actions_kb(search_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Actions for a specific search: pause/resume, filters, delete, back."""
    b = InlineKeyboardBuilder()
    if is_active:
        b.button(text="⏸ Пауза", callback_data=SearchCB(action="pause", sid=search_id))
    else:
        b.button(text="▶️ Возобновить", callback_data=SearchCB(action="resume", sid=search_id))
    b.button(text="🔍 Фильтры", callback_data=SearchCB(action="filters", sid=search_id))
    b.button(text="🗑 Удалить", callback_data=SearchCB(action="delete", sid=search_id))
    b.button(text="◀️ Мои поиски", callback_data=MenuCB(action="searches"))
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(2, 1, 2)
    return b.as_markup()


def after_add_kb(search_id: int) -> InlineKeyboardMarkup:
    """Shown after a search is successfully added."""
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Открыть фильтры", callback_data=SearchCB(action="filters", sid=search_id))
    b.button(text="📋 Мои поиски", callback_data=MenuCB(action="searches"))
    b.button(text="➕ Добавить ещё", callback_data=MenuCB(action="add_start"))
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(1, 2, 1)
    return b.as_markup()


def after_action_kb() -> InlineKeyboardMarkup:
    """Shown after pause/resume/delete."""
    b = InlineKeyboardBuilder()
    b.button(text="📋 Мои поиски", callback_data=MenuCB(action="searches"))
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(2)
    return b.as_markup()


def error_kb(back_search_id: int = 0) -> InlineKeyboardMarkup:
    """Shown after an error; offers Back (to search or list) and Menu."""
    b = InlineKeyboardBuilder()
    if back_search_id:
        b.button(
            text="◀️ Назад к поиску",
            callback_data=SearchCB(action="view", sid=back_search_id),
        )
    b.button(text="📋 Мои поиски", callback_data=MenuCB(action="searches"))
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()
