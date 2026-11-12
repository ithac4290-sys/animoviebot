from aiogram import Router
from bot.handlers.users import router as users_router
from bot.handlers.admin import router as admin_router
from bot.handlers.inline_search import router as inline_router


def setup_routers() -> Router:
    main_router = Router()
    # Tartib muhim: avval admin, keyin inline, keyin users
    main_router.include_router(admin_router)
    main_router.include_router(inline_router)
    main_router.include_router(users_router)
    return main_router
