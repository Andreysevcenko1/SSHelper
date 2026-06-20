from aiogram import Router

from app.bot.handlers.common import router as common_router
from app.bot.handlers.searches import router as searches_router


def get_main_router() -> Router:
    router = Router()
    router.include_router(common_router)
    router.include_router(searches_router)
    return router
