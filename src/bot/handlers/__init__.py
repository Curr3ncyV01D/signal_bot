from aiogram import Router
from .commands import router as commands_router
from .settings import router as settings_router

# Собираем все роутеры в один главный
main_router = Router()
main_router.include_routers(commands_router, settings_router)