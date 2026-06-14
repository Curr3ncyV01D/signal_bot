from aiogram import Router
from .commands import router as commands_router
from .settings import router as settings_router
from .join_requests import router as join_requests_router
from .common import router as common_router
from .admin import router as admin_router
from .admin_bi import router as admin_bi_router
from .admin_broadcast import router as admin_broadcast_router
from .wallet import router as wallet_router
from .shop import router as shop_router

# Собираем все роутеры в один главный
main_router = Router()
main_router.include_routers(
    commands_router, 
    settings_router, 
    join_requests_router, 
    common_router, 
    admin_router,
    admin_bi_router,
    admin_broadcast_router,
    wallet_router,
    shop_router
)
