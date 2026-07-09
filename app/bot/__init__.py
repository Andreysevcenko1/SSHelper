from aiogram import Router

from app.bot.handlers.common import router as common_router
from app.bot.handlers.searches import router as searches_router
from app.bot.handlers.add_search import router as add_search_router
from app.bot.handlers.filter_cmds import router as filter_cmds_router
from app.bot.handlers.group_admin import router as group_admin_router
from app.bot.handlers.lang import router as lang_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.subscription import router as subscription_router


def get_main_router() -> Router:
    router = Router()
    # Command handlers first so they take priority over FSM text fallbacks
    router.include_router(common_router)
    router.include_router(lang_router)
    router.include_router(add_search_router)
    router.include_router(searches_router)
    router.include_router(filter_cmds_router)
    router.include_router(group_admin_router)
    router.include_router(subscription_router)
    # Callback handlers
    router.include_router(menu_router)
    return router
