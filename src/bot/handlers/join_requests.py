import logging
from aiogram import Router, types
from aiogram.exceptions import TelegramForbiddenError

from src.database.session import async_session
from src.database.models import User
from src.database.functions import get_utc_now

logger = logging.getLogger(__name__)
router = Router()

@router.chat_join_request()
async def process_join_request(request: types.ChatJoinRequest):
    """Обработчик заявок на вступление в закрытый канал"""
    
    async with async_session() as session:
        user = await session.get(User, request.from_user.id)
        now = get_utc_now()
        
        # Проверяем, есть ли юзер в базе и активна ли его подписка/триал
        is_active = user and user.subscription_end and user.subscription_end > now
        
        if is_active:
            try:
                # Одобряем заявку
                await request.approve()
                logger.info(f"✅ Одобрена заявка в канал для пользователя {request.from_user.id}")
            except Exception as e:
                logger.error(f"Ошибка при одобрении заявки {request.from_user.id}: {e}")
        else:
            try:
                # Отклоняем заявку
                await request.decline()
                logger.info(f"❌ Отклонена заявка в канал для пользователя {request.from_user.id} (нет подписки)")
                
                # Пытаемся написать в ЛС причину
                text = (
                    "❌ <b>Ваша заявка на вступление отклонена.</b>\n\n"
                    "У вас нет активной подписки или пробного периода. "
                    "Пожалуйста, перейдите в бота и нажмите /start для приобритения подписки."
                )
                await request.bot.send_message(
                    chat_id=request.from_user.id,
                    text=text,
                    parse_mode="HTML"
                )
            except TelegramForbiddenError:
                # Юзер заблокировал бота или ни разу ему не писал (бот не может писать первым)
                logger.warning(f"Не удалось отправить уведомление {request.from_user.id}: этот пользователь недоступен боту.")
            except Exception as e:
                logger.error(f"Ошибка при отклонении заявки {request.from_user.id}: {e}")