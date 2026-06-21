from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="m"):
    """Main menu navigation."""
    action: str  # main | searches | add_start | lang | help


class LangCB(CallbackData, prefix="lng"):
    """Language selection."""
    lang: str  # lv | ru | en


class SearchCB(CallbackData, prefix="s"):
    """Search item actions."""
    action: str  # view | pause | resume | delete | filters
    sid: int


class FilterCB(CallbackData, prefix="f"):
    """Filter menu actions."""
    action: str  # show | del_start | edit_start | clear
    sid: int


class FilterDelCB(CallbackData, prefix="fd"):
    """Delete a single filter key."""
    sid: int
    key: str  # filter field key, max 40 chars for callback safety


class FilterEditCB(CallbackData, prefix="fe"):
    """Select a filter field to edit."""
    sid: int
    fidx: int  # index in the sorted schema field list
    pg: int    # page index (for back-navigation to the same page)


class FilterOptCB(CallbackData, prefix="fo"):
    """Select an option value for a filter field."""
    sid: int
    fidx: int  # field index
    vidx: int  # option index
    pg: int    # options page


class PageCB(CallbackData, prefix="pg"):
    """Generic pagination for field/option lists."""
    ctx: str   # "fields" | "opts"
    sid: int
    fidx: int  # -1 when ctx="fields"
    pg: int    # target page number
