from aiogram import Router
from .onboarding import router as onboarding_router
from .commands import router as commands_router
from .settings import router as settings_router
from .common import router as common_router
from .admin import router as admin_router
from .admin_bi import router as admin_bi_router
from .admin_broadcast import router as admin_broadcast_router
from .wallet import router as wallet_router
from .shop import router as shop_router

# Собираем все роутеры в один главный
main_router = Router()
main_router.include_routers(
    onboarding_router,
    commands_router, 
    wallet_router,
    shop_router,
    settings_router, 
    common_router, 
    admin_router,
    admin_bi_router,
    admin_broadcast_router
)
