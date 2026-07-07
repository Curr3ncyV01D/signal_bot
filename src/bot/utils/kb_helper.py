from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardButton


class Kb_Helper:
    @staticmethod
    def add_common_buttons(
        builder: InlineKeyboardBuilder, 
        back_data: str = None, 
        close: bool = True
    ):
        """
        Добавляет стандартные кнопки в конец клавиатуры.
        :param builder: Текущий объект InlineKeyboardBuilder
        :param back_data: callback_data для кнопки Назад (если нужна)
        :param close: Добавлять ли кнопку Закрыть
        """
        # Если нужна кнопка Назад, добавляем её в новый ряд
        if back_data:
            builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data=back_data))
        
        # Если нужна кнопка Закрыть, добавляем её (в новый ряд или к кнопке Назад)
        if close:
            # .row() гарантирует, что кнопка будет на новой строке
            builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-close"), callback_data="common_close"))
        
        return builder

    @staticmethod
    def toggle_icon(status: bool) -> str:
        return "✅" if status else "❌"
