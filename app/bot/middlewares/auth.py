from aiogram import BaseMiddleware

from app.services.ride import RideService

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        ride_service: RideService = data["ride_service"]
        telegram_id = int(event.from_user.id)

        user = await ride_service.get_user_by_id(id=telegram_id)
        
        if not user or not user.is_active:
            await event.answer(
                "⛔ Доступ запрещён.\n"+
                "Вы не зарегистрированы администратором."
            )
            return
        
        data["user"] = user
        return await handler(event, data)
    

