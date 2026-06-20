from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import (
    FilterCB,
    FilterDelCB,
    FilterEditCB,
    FilterOptCB,
    MenuCB,
    PageCB,
    SearchCB,
)

_PAGE_SIZE_FIELDS = 8
_PAGE_SIZE_OPTS = 8


def filters_menu_kb(search_id: int, has_filters: bool) -> InlineKeyboardMarkup:
    """Top-level filter menu for a search."""
    b = InlineKeyboardBuilder()
    b.button(
        text="📋 Показать фильтры",
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(
        text="✏️ Изменить / добавить фильтр",
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    if has_filters:
        b.button(
            text="🗑 Очистить все фильтры",
            callback_data=FilterCB(action="clear", sid=search_id),
        )
    b.button(
        text="◀️ К поиску",
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def filter_items_kb(search_id: int, filters: dict) -> InlineKeyboardMarkup:
    """Shows current active filters, each with a 🗑 delete button."""
    b = InlineKeyboardBuilder()
    for key, value in filters.items():
        display = f"{key} = {value}"
        if len(display) > 32:
            display = display[:30] + "…"
        # Truncate key to 40 chars for callback safety
        safe_key = key[:40]
        b.button(
            text=f"🗑 {display}",
            callback_data=FilterDelCB(sid=search_id, key=safe_key),
        )
    b.button(
        text="✏️ Изменить / добавить фильтр",
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(
        text="🗑 Очистить все",
        callback_data=FilterCB(action="clear", sid=search_id),
    )
    b.button(
        text="◀️ К поиску",
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def filter_fields_kb(
    search_id: int,
    fields: list[tuple[int, str, str]],  # (global_idx, name, label)
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Paginated list of filter schema fields for selection."""
    b = InlineKeyboardBuilder()
    start = page * _PAGE_SIZE_FIELDS
    end = start + _PAGE_SIZE_FIELDS
    page_fields = fields[start:end]

    for idx, _name, label in page_fields:
        display = label or _name
        if len(display) > 32:
            display = display[:30] + "…"
        b.button(
            text=display,
            callback_data=FilterEditCB(sid=search_id, fidx=idx, pg=page),
        )

    # Pagination nav
    nav = []
    if page > 0:
        nav.append(
            ("◀️ Пред.", PageCB(ctx="fields", sid=search_id, fidx=-1, pg=page - 1))
        )
    if end < len(fields):
        nav.append(
            ("След. ▶️", PageCB(ctx="fields", sid=search_id, fidx=-1, pg=page + 1))
        )
    for label, cb in nav:
        b.button(text=label, callback_data=cb)

    b.button(
        text="◀️ К фильтрам",
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))

    # Build row sizes: fields 2 per row, nav row, back row
    row_sizes: list[int] = []
    n = len(page_fields)
    row_sizes += [2] * (n // 2)
    if n % 2:
        row_sizes.append(1)
    if nav:
        row_sizes.append(len(nav))
    row_sizes.append(2)

    b.adjust(*row_sizes)
    return b.as_markup()


def filter_options_kb(
    search_id: int,
    fidx: int,
    options: list[dict],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Paginated list of select options for a specific filter field."""
    b = InlineKeyboardBuilder()
    start = page * _PAGE_SIZE_OPTS
    end = start + _PAGE_SIZE_OPTS
    page_opts = options[start:end]

    for i, opt in enumerate(page_opts):
        vidx = start + i
        text = str(opt.get("text") or opt.get("value") or vidx)
        if len(text) > 32:
            text = text[:30] + "…"
        b.button(
            text=text,
            callback_data=FilterOptCB(sid=search_id, fidx=fidx, vidx=vidx, pg=page),
        )

    nav = []
    if page > 0:
        nav.append(
            ("◀️ Пред.", PageCB(ctx="opts", sid=search_id, fidx=fidx, pg=page - 1))
        )
    if end < len(options):
        nav.append(
            ("След. ▶️", PageCB(ctx="opts", sid=search_id, fidx=fidx, pg=page + 1))
        )
    for label, cb in nav:
        b.button(text=label, callback_data=cb)

    b.button(
        text="◀️ К полям",
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))

    row_sizes: list[int] = []
    n = len(page_opts)
    row_sizes += [2] * (n // 2)
    if n % 2:
        row_sizes.append(1)
    if nav:
        row_sizes.append(len(nav))
    row_sizes.append(2)

    b.adjust(*row_sizes)
    return b.as_markup()


def after_filter_kb(search_id: int) -> InlineKeyboardMarkup:
    """Shown after setting/deleting/clearing a filter."""
    b = InlineKeyboardBuilder()
    b.button(
        text="📋 Показать фильтры",
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(
        text="✏️ Изменить ещё",
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(
        text="◀️ К поиску",
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text="🏠 В меню", callback_data=MenuCB(action="main"))
    b.adjust(2, 2)
    return b.as_markup()


def cancel_kb(search_id: int = 0) -> InlineKeyboardMarkup:
    """Used during FSM steps to allow cancellation."""
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=MenuCB(action="main"))
    if search_id:
        b.button(
            text="◀️ К поиску",
            callback_data=SearchCB(action="view", sid=search_id),
        )
    b.adjust(1)
    return b.as_markup()
