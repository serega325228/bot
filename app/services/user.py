import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.models.user import User, UserRole
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    """Базовое исключение для UserService."""
    pass


class UserNotFoundError(UserServiceError):
    """Пользователь не найден."""
    pass


class UserAlreadyExistsError(UserServiceError):
    """Пользователь уже существует."""
    pass


class UserService:
    """Сервис для управления пользователями."""

    def __init__(self, *, user_repo: UserRepository):
        self.__user_repo = user_repo

    async def get_user_by_id(self, *, id: int) -> User | None:
        """Получить пользователя по ID."""
        try:
            return await self.__user_repo.get_by_id(id=id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователя {id}: {e}")
            return None

    async def get_all_users(self) -> list[User]:
        """Получить всех пользователей."""
        try:
            return await self.__user_repo.get_all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении всех пользователей: {e}")
            return []

    async def get_users_by_ride(self, *, ride_id: uuid.UUID) -> list[User]:
        """Получить пользователей по поездке."""
        try:
            return await self.__user_repo.get_users_by_ride(ride_id=ride_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователей поездки {ride_id}: {e}")
            return []

    async def create_user(
        self,
        *,
        id: int,
        full_name: str,
        role: UserRole = UserRole.PASSENGER,
        nickname: str = ""
    ) -> None:
        """Создать нового пользователя."""
        try:
            existing = await self.get_user_by_id(id=id)
            if existing:
                raise UserAlreadyExistsError(f"User {id} already exist")

            user = User(
                id=id,
                full_name=full_name,
                nickname=nickname,
                role=role,
                is_active=True,
            )
            await self.__user_repo.create(user=user)
            logger.info(f"Пользователь {id} ({full_name}) успешно создан")
        except UserAlreadyExistsError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось создать пользователя: {e}")

    async def activate_user(self, *, id: int) -> None:
        """Активировать пользователя."""
        try:
            user = await self.get_user_by_id(id=id)
            if not user:
                raise UserNotFoundError(f"User {id} not found")
            if not user.is_active:
                user.is_active = True
                await self.__user_repo.save(user=user)
                logger.info(f"Пользователь {id} активирован")
        except UserNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при активации пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось активировать пользователя: {e}")

    async def deactivate_user(self, *, id: int) -> None:
        """Деактивировать пользователя."""
        try:
            user = await self.get_user_by_id(id=id)
            if not user:
                raise UserNotFoundError(f"User {id} not found")
            if user.is_active:
                user.is_active = False
                await self.__user_repo.save(user=user)
                logger.info(f"Пользователь {id} деактивирован")
        except UserNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при деактивации пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось деактивировать пользователя: {e}")

    async def delete_user(self, *, id: int) -> None:
        """Удалить пользователя."""
        try:
            await self.__user_repo.delete(id=id)
            logger.info(f"Пользователь {id} удалён")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось удалить пользователя: {e}")

    async def change_role(self, *, id: int, role: UserRole) -> None:
        """Изменить роль пользователя."""
        try:
            user = await self.get_user_by_id(id=id)
            if not user:
                raise UserNotFoundError(f"User {id} not found")
            await self.__user_repo.change_role(id=id, role=role)
            logger.info(f"Пользователю {id} установлена роль {role.value}")
        except UserNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении роли пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось изменить роль: {e}")

    async def change_nickname(self, *, id: int, nickname: str) -> None:
        """Изменить никнейм пользователя."""
        try:
            await self.__user_repo.change_nickname(id=id, nickname=nickname)
            logger.info(f"Пользователю {id} установлен никнейм {nickname}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении никнейма пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось изменить никнейм: {e}")

    async def change_full_name(self, *, id: int, full_name: str) -> None:
        """Изменить ФИО пользователя."""
        try:
            await self.__user_repo.change_full_name(id=id, full_name=full_name)
            logger.info(f"Пользователю {id} изменено ФИО на {full_name}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении ФИО пользователя {id}: {e}")
            raise UserServiceError(f"Не удалось изменить ФИО: {e}")

    async def make_passenger(self, *, id: int) -> None:
        """Сделать пользователя пассажиром."""
        await self.change_role(id=id, role=UserRole.PASSENGER)

    async def make_admin(self, *, id: int) -> None:
        """Сделать пользователя администратором."""
        await self.change_role(id=id, role=UserRole.ADMIN)

    async def make_driver(self, *, id: int) -> None:
        """Сделать пользователя водителем."""
        await self.change_role(id=id, role=UserRole.DRIVER)
