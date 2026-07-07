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
from app.i18n import get_text
from app.services.filters import filter_display_label, filter_value_label, sanitize_personal_ui_text

_PAGE_SIZE_FIELDS = 8
_PAGE_SIZE_OPTS = 8


def filters_menu_kb(search_id: int, has_filters: bool, lang: str = "lv") -> InlineKeyboardMarkup:
    """Top-level filter menu for a search (⚙️ Фильтры sub-menu)."""
    b = InlineKeyboardBuilder()
    b.button(
        text=get_text("btn_show_filters", lang),
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(
        text=get_text("btn_edit_filter", lang),
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    if has_filters:
        b.button(
            text=get_text("btn_del_filter", lang),
            callback_data=FilterCB(action="del_start", sid=search_id),
        )
        b.button(
            text=get_text("btn_clear_filters", lang),
            callback_data=FilterCB(action="clear", sid=search_id),
        )
    b.button(
        text=get_text("btn_back_to_search", lang),
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def filter_items_kb(
    search_id: int,
    filters: dict,
    lang: str = "lv",
    schema: dict | None = None,
    profile: str | None = None,
) -> InlineKeyboardMarkup:
    """Shows current active filters, each with a 🗑 delete button."""
    b = InlineKeyboardBuilder()
    for key, value in filters.items():
        label = filter_display_label(key, schema, lang, profile=profile)
        value_label = filter_value_label(key, value, locale=lang, profile=profile, schema=schema)
        display = sanitize_personal_ui_text(f"{label} = {value_label}", locale=lang, profile=profile)
        if len(display) > 32:
            display = display[:30] + "…"
        # Truncate key to 40 chars for callback safety
        safe_key = key[:40]
        b.button(
            text=f"🗑 {display}",
            callback_data=FilterDelCB(sid=search_id, key=safe_key),
        )
    b.button(
        text=get_text("btn_edit_filter", lang),
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(
        text=get_text("btn_clear_filters", lang),
        callback_data=FilterCB(action="clear", sid=search_id),
    )
    b.button(
        text=get_text("btn_back_to_search", lang),
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def no_filters_kb(search_id: int, lang: str = "lv") -> InlineKeyboardMarkup:
    """Shown when no filters are set (empty state)."""
    b = InlineKeyboardBuilder()
    b.button(
        text=get_text("btn_edit_filter", lang),
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(
        text=get_text("btn_back_to_search", lang),
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(1)
    return b.as_markup()


def filter_fields_kb(
    search_id: int,
    fields: list[tuple[int, str, str]],  # (global_idx, name, label)
    page: int = 0,
    lang: str = "lv",
) -> InlineKeyboardMarkup:
    """Paginated list of filter schema fields for selection."""
    b = InlineKeyboardBuilder()
    start = page * _PAGE_SIZE_FIELDS
    end = start + _PAGE_SIZE_FIELDS
    page_fields = fields[start:end]

    for idx, _name, label in page_fields:
        display = sanitize_personal_ui_text(label, locale=lang)
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
            (get_text("btn_prev_page", lang), PageCB(ctx="fields", sid=search_id, fidx=-1, pg=page - 1))
        )
    if end < len(fields):
        nav.append(
            (get_text("btn_next_page", lang), PageCB(ctx="fields", sid=search_id, fidx=-1, pg=page + 1))
        )
    for label, cb in nav:
        b.button(text=label, callback_data=cb)

    b.button(
        text=get_text("btn_back_to_search", lang),
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))

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
    lang: str = "lv",
) -> InlineKeyboardMarkup:
    """Paginated list of select options for a specific filter field."""
    b = InlineKeyboardBuilder()
    start = page * _PAGE_SIZE_OPTS
    end = start + _PAGE_SIZE_OPTS
    page_opts = options[start:end]

    for i, opt in enumerate(page_opts):
        vidx = start + i
        text = str(opt.get("display_text") or opt.get("text") or opt.get("value") or vidx)
        text = sanitize_personal_ui_text(text, locale=lang)
        if len(text) > 32:
            text = text[:30] + "…"
        b.button(
            text=text,
            callback_data=FilterOptCB(sid=search_id, fidx=fidx, vidx=vidx, pg=page),
        )

    nav = []
    if page > 0:
        nav.append(
            (get_text("btn_prev_page", lang), PageCB(ctx="opts", sid=search_id, fidx=fidx, pg=page - 1))
        )
    if end < len(options):
        nav.append(
            (get_text("btn_next_page", lang), PageCB(ctx="opts", sid=search_id, fidx=fidx, pg=page + 1))
        )
    for label, cb in nav:
        b.button(text=label, callback_data=cb)

    b.button(
        text=get_text("btn_back", lang),
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))

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


def after_filter_kb(search_id: int, lang: str = "lv") -> InlineKeyboardMarkup:
    """Shown after setting/deleting/clearing a filter."""
    b = InlineKeyboardBuilder()
    b.button(
        text=get_text("btn_show_filters", lang),
        callback_data=FilterCB(action="show", sid=search_id),
    )
    b.button(
        text=get_text("btn_edit_more", lang),
        callback_data=FilterCB(action="edit_start", sid=search_id),
    )
    b.button(
        text=get_text("btn_back_to_search", lang),
        callback_data=SearchCB(action="view", sid=search_id),
    )
    b.button(text=get_text("btn_back_to_menu", lang), callback_data=MenuCB(action="main"))
    b.adjust(2, 2)
    return b.as_markup()


def cancel_kb(search_id: int = 0, lang: str = "lv") -> InlineKeyboardMarkup:
    """Used during FSM steps to allow cancellation."""
    b = InlineKeyboardBuilder()
    b.button(text=get_text("btn_cancel", lang), callback_data=MenuCB(action="main"))
    if search_id:
        b.button(
            text=get_text("btn_back_to_search", lang),
            callback_data=SearchCB(action="view", sid=search_id),
        )
    b.adjust(1)
    return b.as_markup()
