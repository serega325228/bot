import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.models.stop import Stop
from app.repositories.stop import StopRepository

logger = logging.getLogger(__name__)


class StopServiceError(Exception):
    """Базовое исключение для StopService."""
    pass


class StopNotFoundError(StopServiceError):
    """Остановка не найдена."""
    pass


class StopAlreadyExistsError(StopServiceError):
    """Остановка уже существует."""
    pass


class StopService:
    """Сервис для управления остановками."""

    def __init__(self, *, stop_repo: StopRepository):
        self.__stop_repo = stop_repo

    async def get_stop_by_id(self, *, stop_id: uuid.UUID) -> Stop | None:
        """Получить остановку по ID."""
        try:
            return await self.__stop_repo.get_by_id(id=stop_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении остановки {stop_id}: {e}")
            return None

    async def get_stop_by_name(self, *, name: str) -> Stop | None:
        """Получить остановку по названию."""
        try:
            return await self.__stop_repo.get_by_name(name=name)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении остановки по имени {name}: {e}")
            return None

    async def get_all_stops(self) -> list[Stop]:
        """Получить все остановки."""
        try:
            return await self.__stop_repo.get_all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении всех остановок: {e}")
            return []

    async def get_active_stops(self) -> list[Stop]:
        """Получить активные остановки."""
        try:
            return await self.__stop_repo.get_active()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активных остановок: {e}")
            return []

    async def get_stop_by_order(self, *, order: int) -> Stop | None:
        """Получить остановку по порядковому номеру."""
        try:
            return await self.__stop_repo.get_by_order(order=order)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении остановки по порядку {order}: {e}")
            return None
        except Exception as e:
            logger.error(f"Остановка с порядком {order} не найдена: {e}")
            return None

    async def create_stop(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        order: int,
    ) -> None:
        """Создать новую остановку."""
        try:
            stop = Stop(
                name=name,
                latitude=latitude,
                longitude=longitude,
                order=order,
            )
            await self.__stop_repo.create(stop=stop)
            logger.info(f"Остановка {name} (order={order}) успешно создана")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании остановки {name}: {e}")
            raise StopServiceError(f"Не удалось создать остановку: {e}")

    async def activate_stop(self, *, id: uuid.UUID) -> None:
        """Активировать остановку."""
        try:
            stop = await self.get_stop_by_id(stop_id=id)
            if not stop:
                raise StopNotFoundError(f"Stop {id} not found")
            if not stop.is_active:
                stop.is_active = True
                await self.__stop_repo.save(stop=stop)
                logger.info(f"Остановка {id} активирована")
        except StopNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при активации остановки {id}: {e}")
            raise StopServiceError(f"Не удалось активировать остановку: {e}")

    async def deactivate_stop(self, *, id: uuid.UUID) -> None:
        """Деактивировать остановку."""
        try:
            stop = await self.get_stop_by_id(stop_id=id)
            if not stop:
                raise StopNotFoundError(f"Stop {id} not found")
            if stop.is_active:
                stop.is_active = False
                await self.__stop_repo.save(stop=stop)
                logger.info(f"Остановка {id} деактивирована")
        except StopNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при деактивации остановки {id}: {e}")
            raise StopServiceError(f"Не удалось деактивировать остановку: {e}")

    async def delete_stop(self, *, id: uuid.UUID) -> None:
        """Удалить остановку."""
        try:
            await self.__stop_repo.delete(id=id)
            logger.info(f"Остановка {id} удалена")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении остановки {id}: {e}")
            raise StopServiceError(f"Не удалось удалить остановку: {e}")

    async def change_stop_name(self, *, id: uuid.UUID, name: str) -> None:
        """Изменить название остановки."""
        try:
            stop = await self.get_stop_by_id(stop_id=id)
            if not stop:
                raise StopNotFoundError(f"Stop {id} not found")
            await self.__stop_repo.update_name(id=id, name=name)
            logger.info(f"Остановке {id} изменено название на {name}")
        except StopNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении названия остановки {id}: {e}")
            raise StopServiceError(f"Не удалось изменить название остановки: {e}")

    async def change_stop_coordinates(
        self,
        *,
        id: uuid.UUID,
        latitude: float,
        longitude: float
    ) -> None:
        """Изменить координаты остановки."""
        try:
            stop = await self.get_stop_by_id(stop_id=id)
            if not stop:
                raise StopNotFoundError(f"Stop {id} not found")
            stop.latitude = latitude
            stop.longitude = longitude
            await self.__stop_repo.save(stop=stop)
            logger.info(f"Остановке {id} изменены координаты на ({latitude}, {longitude})")
        except StopNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении координат остановки {id}: {e}")
            raise StopServiceError(f"Не удалось изменить координаты остановки: {e}")

    async def change_stop_order(self, *, id: uuid.UUID, order: int) -> None:
        """Изменить порядковый номер остановки."""
        try:
            stop = await self.get_stop_by_id(stop_id=id)
            if not stop:
                raise StopNotFoundError(f"Stop {id} not found")
            stop.order = order
            await self.__stop_repo.save(stop=stop)
            logger.info(f"Остановке {id} изменён порядок на {order}")
        except StopNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при изменении порядка остановки {id}: {e}")
            raise StopServiceError(f"Не удалось изменить порядок остановки: {e}")
