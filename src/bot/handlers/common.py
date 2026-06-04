from aiogram import Router, types, F

router = Router()

@router.callback_query(F.data == "common_close")
async def process_common_close(callback: types.CallbackQuery):
    await callback.message.delete()