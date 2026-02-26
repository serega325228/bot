import uuid

from app.models.user import User, UserRole
from app.repositories.user import UserRepository


class UserService:
    """Сервис для управления пользователями."""

    def __init__(self, *, user_repo: UserRepository):
        self.__user_repo = user_repo

    async def get_user_by_id(self, *, id: int) -> User | None:
        """Получить пользователя по ID."""
        return await self.__user_repo.get_by_id(id=id)

    async def get_all_users(self) -> list[User]:
        """Получить всех пользователей."""
        return await self.__user_repo.get_all()

    async def get_users_by_ride(self, *, ride_id: uuid.UUID) -> list[User]:
        """Получить пользователей по поездке."""
        return await self.__user_repo.get_users_by_ride(ride_id=ride_id)

    async def create_user(
        self,
        *,
        id: int,
        full_name: str,
        role: UserRole = UserRole.PASSENGER,
        nickname: str = ""
    ) -> None:
        """Создать нового пользователя."""
        existing = await self.get_user_by_id(id=id)
        if existing:
            raise ValueError("User already exist")

        user = User(
            id=id,
            full_name=full_name,
            nickname=nickname,
            role=role,
            is_active=True,
        )
        await self.__user_repo.create(user=user)

    async def activate_user(self, *, id: int) -> None:
        """Активировать пользователя."""
        user = await self.get_user_by_id(id=id)
        if user and not user.is_active:
            user.is_active = True
            await self.__user_repo.save(user=user)

    async def deactivate_user(self, *, id: int) -> None:
        """Деактивировать пользователя."""
        user = await self.get_user_by_id(id=id)
        if user and user.is_active:
            user.is_active = False
            await self.__user_repo.save(user=user)

    async def delete_user(self, *, id: int) -> None:
        """Удалить пользователя."""
        await self.__user_repo.delete(id=id)

    async def change_role(self, *, id: int, role: UserRole) -> None:
        """Изменить роль пользователя."""
        await self.__user_repo.change_role(id=id, role=role)

    async def change_nickname(self, *, id: int, nickname: str) -> None:
        """Изменить никнейм пользователя."""
        await self.__user_repo.change_nickname(id=id, nickname=nickname)

    async def change_full_name(self, *, id: int, full_name: str) -> None:
        """Изменить ФИО пользователя."""
        await self.__user_repo.change_full_name(id=id, full_name=full_name)

    async def make_passenger(self, *, id: int) -> None:
        """Сделать пользователя пассажиром."""
        await self.change_role(id=id, role=UserRole.PASSENGER)

    async def make_admin(self, *, id: int) -> None:
        """Сделать пользователя администратором."""
        await self.change_role(id=id, role=UserRole.ADMIN)

    async def make_driver(self, *, id: int) -> None:
        """Сделать пользователя водителем."""
        await self.change_role(id=id, role=UserRole.DRIVER)
