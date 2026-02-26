import uuid

from app.models.stop import Stop
from app.repositories.stop import StopRepository


class StopService:
    """Сервис для управления остановками."""

    def __init__(self, *, stop_repo: StopRepository):
        self.__stop_repo = stop_repo

    async def get_stop_by_id(self, *, stop_id: uuid.UUID) -> Stop | None:
        """Получить остановку по ID."""
        return await self.__stop_repo.get_by_id(id=stop_id)

    async def get_stop_by_name(self, *, name: str) -> Stop | None:
        """Получить остановку по названию."""
        return await self.__stop_repo.get_by_name(name=name)

    async def get_all_stops(self) -> list[Stop]:
        """Получить все остановки."""
        return await self.__stop_repo.get_all()

    async def get_active_stops(self) -> list[Stop]:
        """Получить активные остановки."""
        return await self.__stop_repo.get_active()

    async def get_stop_by_order(self, *, order: int) -> Stop:
        """Получить остановку по порядковому номеру."""
        return await self.__stop_repo.get_by_order(order=order)

    async def create_stop(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        order: int,
    ) -> None:
        """Создать новую остановку."""
        stop = Stop(
            name=name,
            latitude=latitude,
            longitude=longitude,
            order=order,
        )
        await self.__stop_repo.create(stop=stop)

    async def activate_stop(self, *, id: uuid.UUID) -> None:
        """Активировать остановку."""
        stop = await self.get_stop_by_id(stop_id=id)
        if stop and not stop.is_active:
            stop.is_active = True
            await self.__stop_repo.save(stop=stop)

    async def deactivate_stop(self, *, id: uuid.UUID) -> None:
        """Деактивировать остановку."""
        stop = await self.get_stop_by_id(stop_id=id)
        if stop and stop.is_active:
            stop.is_active = False
            await self.__stop_repo.save(stop=stop)

    async def delete_stop(self, *, id: uuid.UUID) -> None:
        """Удалить остановку."""
        await self.__stop_repo.delete(id=id)

    async def change_stop_name(self, *, id: uuid.UUID, name: str) -> None:
        """Изменить название остановки."""
        await self.__stop_repo.update_name(id=id, name=name)

    async def change_stop_coordinates(
        self,
        *,
        id: uuid.UUID,
        latitude: float,
        longitude: float
    ) -> None:
        """Изменить координаты остановки."""
        stop = await self.get_stop_by_id(stop_id=id)
        if stop:
            stop.latitude = latitude
            stop.longitude = longitude
            await self.__stop_repo.save(stop=stop)

    async def change_stop_order(self, *, id: uuid.UUID, order: int) -> None:
        """Изменить порядковый номер остановки."""
        stop = await self.get_stop_by_id(stop_id=id)
        if stop:
            stop.order = order
            await self.__stop_repo.save(stop=stop)
