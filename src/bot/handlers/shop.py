import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.utils.markdown import hbold

from src.core.config import config
from src.database.session import async_session
from src.database.crud import user_service, billing_service
from src.database.functions import get_utc_now
from src.bot.keyboards.billing_kb import get_subscription_tariffs_kb
from src.bot.keyboards import get_close_button_kb
from src.database.models import User

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: types.CallbackQuery):
    """Меню выбора тарифа"""
    text = (
        f"💎 <b>VIP-Подписка</b>\n\n"
        f"Преимущества VIP-доступа:\n"
        f"• Доступ в закрытый канал с алертами\n"
        f"• Персональные настройки в боте\n"
        f"• Аналитика в реальном времени\n\n"
        f"Выберите подходящий тариф:"
    )
    await callback.message.edit_text(text, reply_markup=get_subscription_tariffs_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_plan_"))
async def callback_process_purchase(callback: types.CallbackQuery):
    """Процесс покупки подписки с баланса"""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer("❌ Некорректные параметры тарифа.", show_alert=True)
        
    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id
    
    if not price:
        return await callback.answer("Ошибка: Тариф не найден.", show_alert=True)
        
    async with async_session() as session:
        # Атомарная покупка (проверка баланса, списание, продление, транзакция)
        success, new_end = await billing_service.purchase_subscription(
            session=session,
            user_id=user_id,
            days=days,
            price=price
        )
        
        if not success:
            return await callback.answer("❌ Недостаточно средств на балансе.", show_alert=True)

        purchaser = await session.get(User, user_id)
        referrer = None
        bonus_amount = round(float(price) * (config.REFERRAL_BONUS_PERCENT / 100.0), 2)
        if purchaser and purchaser.referrer_id and bonus_amount > 0:
            referrer = await session.get(User, purchaser.referrer_id)
        
        # 3. Выдаем ссылку на канал (если бот админ)
        try:
            invite_link = await callback.bot.create_chat_invite_link(
                chat_id=config.PRIVATE_CHANNEL_ID,
                name=f"Sub_{user_id}",
                creates_join_request=True
            )
            link_text = f"\n\n👉 {hbold('Ваша ссылка для входа:')}\n{invite_link.invite_link}"
        except Exception as e:
            logger.error(f"Ошибка создания ссылки: {e}")
            link_text = "\n\n<i>(Ошибка: Бот не смог создать ссылку. Обратитесь к админу.)</i>"
            
        text = (
            f"🎉 <b>Подписка успешно оформлена!</b>\n\n"
            f"Тариф: {hbold(f'{days} дней')}\n"
            f"Действует до: {hbold(new_end.strftime('%d.%m.%Y %H:%M'))}"
            f"{link_text}"
        )
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer("Поздравляем!")

        if referrer:
            try:
                await callback.bot.send_message(
                    chat_id=referrer.id,
                    text=(
                        "🤝 <b>Партнерский бонус начислен!</b>\n\n"
                        f"Ваш реферал совершил покупку, и вам начислено {hbold(f'{bonus_amount:.2f} USDT')}."
                    ),
                    parse_mode="HTML",
                    reply_markup=get_close_button_kb()
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить реферера {referrer.id} о бонусе: {e}")
