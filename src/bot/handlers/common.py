from aiogram import Router, types, F

router = Router()

@router.callback_query(F.data == "common_close")
async def process_common_close(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass

# Игнор для пустых кнопок пагинации
@router.callback_query(F.data == "ignore")
async def process_ignore(callback: types.CallbackQuery):
    await callback.answer()