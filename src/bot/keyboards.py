from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import User

def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    cas = "✅" if user.alert_cascade else "❌"
    vol = "✅" if user.alert_volume else "❌"
    sqz = "✅" if user.alert_squeeze else "❌"

    buttons = [
        [InlineKeyboardButton(text=f"{cas} Каскады", callback_data="toggle_cascade")],
        [InlineKeyboardButton(text=f"{vol} LIQ VOLUME", callback_data="toggle_volume")],
        [InlineKeyboardButton(text=f"{sqz} LIQ SQUEEZE", callback_data="toggle_squeeze")],
        [InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="set_threshold")],
        [InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="set_cascade_threshold")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="close_message")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)