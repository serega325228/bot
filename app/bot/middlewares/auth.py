import logging

from aiogram import BaseMiddleware

from app.services.user import UserService, UserNotFoundError

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки доступа.
    Проверяет, что пользователь существует и активен.
    """
    async def __call__(self, handler, event, data):
        try:
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
        except UserNotFoundError as e:
            logger.warning(f"Пользователь не найден: {e}")
            await event.answer("⛔ Доступ запрещён.\nВы не зарегистрированы.")
        except Exception as e:
            logger.error(f"Ошибка в AuthMiddleware: {e}")
            await event.answer("⛔ Произошла ошибка при проверке доступа.")


class RoleAuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки роли пользователя.
    Используется вместе с фильтрами IsAdmin, IsDriver.
    """
    async def __call__(self, handler, event, data):
        try:
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
        except UserNotFoundError as e:
            logger.warning(f"Пользователь не найден: {e}")
            await event.answer("⛔ Доступ запрещён.\nВы не зарегистрированы.")
        except Exception as e:
            logger.error(f"Ошибка в RoleAuthMiddleware: {e}")
            await event.answer("⛔ Произошла ошибка при проверке доступа.")
