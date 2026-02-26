from aiogram import BaseMiddleware

from app.services.user import UserService

class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки доступа.
    Проверяет, что пользователь существует и активен.
    """
    async def __call__(self, handler, event, data):
        user_service: UserService = data["user_service"]
        telegram_id = int(event.from_user.id)

        user = await user_service.get_user_by_id(id=telegram_id)

        if not user or not user.is_active:
            await event.answer(
                "⛔ Доступ запрещён.\n"
                "Вы не зарегистрированы администратором."
            )
            return

        data["user"] = user
        return await handler(event, data)


class RoleAuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки роли пользователя.
    Используется вместе с фильтрами IsAdmin, IsDriver.
    """
    async def __call__(self, handler, event, data):
        user_service: UserService = data["user_service"]
        telegram_id = int(event.from_user.id)

        user = await user_service.get_user_by_id(id=telegram_id)

        if not user:
            await event.answer(
                "⛔ Доступ запрещён.\n"
                "Вы не зарегистрированы."
            )
            return

        if not user.is_active:
            await event.answer(
                "⛔ Доступ запрещён.\n"
                "Ваш аккаунт деактивирован."
            )
            return

        data["user"] = user
        return await handler(event, data)
    

