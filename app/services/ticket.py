import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.models.ticket import Ticket, TicketStatus
from app.models.ride import Ride, RideStatus
from app.repositories.ticket import TicketRepository
from app.repositories.ride import RideRepository

logger = logging.getLogger(__name__)


class TicketServiceError(Exception):
    """Базовое исключение для TicketService."""
    pass


class TicketNotFoundError(TicketServiceError):
    """Билет не найден."""
    pass


class RideNotFoundError(TicketServiceError):
    """Поездка не найдена."""
    pass


class TicketService:
    """Сервис для управления билетами."""

    def __init__(
        self,
        *,
        ticket_repo: TicketRepository,
        ride_repo: RideRepository,
    ):
        self.__ticket_repo = ticket_repo
        self.__ride_repo = ride_repo

    async def get_active_ticket(self, *, user_id: int) -> Ticket | None:
        """Получить активный билет пользователя."""
        try:
            return await self.__ticket_repo.get_active_ticket(user_id=user_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активного билета пользователя {user_id}: {e}")
            return None

    async def get_ticket_by_id(self, *, ticket_id: uuid.UUID) -> Ticket | None:
        """Получить билет по ID."""
        try:
            return await self.__ticket_repo.get_by_id(ticket_id=ticket_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении билета {ticket_id}: {e}")
            return None

    async def create_or_update_ticket(
        self,
        *,
        stop_id: uuid.UUID,
        user_id: int,
        status: TicketStatus = TicketStatus.PENDING,
    ) -> None:
        """Создать или обновить билет."""
        try:
            ticket = await self.get_active_ticket(user_id=user_id)

            if not ticket:
                ride = await self.__get_first_active_ride()
                if not ride:
                    raise RideNotFoundError("No active ride found")
                
                ticket = Ticket(
                    ride_id=ride.id,
                    stop_id=stop_id,
                    user_id=user_id,
                    status=status,
                )
                await self.__ticket_repo.create(ticket=ticket)
                logger.info(f"Создан билет для пользователя {user_id} на остановке {stop_id}")
            else:
                await self.__ticket_repo.update_ticket_stop(
                    ticket_id=ticket.id,
                    stop_id=stop_id,
                )
                logger.info(f"Обновлена остановка в билете {ticket.id} на {stop_id}")
        except (TicketNotFoundError, RideNotFoundError):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании/обновлении билета пользователя {user_id}: {e}")
            raise TicketServiceError(f"Не удалось создать/обновить билет: {e}")

    async def mark_as_boarded(self, *, ticket_id: uuid.UUID) -> None:
        """Отметить билет как посаженный."""
        try:
            ticket = await self.get_ticket_by_id(ticket_id=ticket_id)
            if not ticket:
                raise TicketNotFoundError(f"Ticket {ticket_id} not found")
            await self.__ticket_repo.change_status(
                ticket_id=ticket_id,
                status=TicketStatus.BOARDED,
            )
            logger.info(f"Билет {ticket_id} отмечен как посаженный")
        except TicketNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при отметке билета {ticket_id} как посаженного: {e}")
            raise TicketServiceError(f"Не удалось отметить билет как посаженный: {e}")

    async def mark_as_absent(self, *, ticket_id: uuid.UUID) -> None:
        """Отметить билет как отсутствующий."""
        try:
            ticket = await self.get_ticket_by_id(ticket_id=ticket_id)
            if not ticket:
                raise TicketNotFoundError(f"Ticket {ticket_id} not found")
            await self.__ticket_repo.change_status(
                ticket_id=ticket_id,
                status=TicketStatus.ABSENT,
            )
            logger.info(f"Билет {ticket_id} отмечен как отсутствующий")
        except TicketNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при отметке билета {ticket_id} как отсутствующего: {e}")
            raise TicketServiceError(f"Не удалось отметить билет как отсутствующий: {e}")

    async def has_waiting_passengers(self, *, stop_id: uuid.UUID) -> bool:
        """Проверить, есть ли ожидающие пассажиры на остановке."""
        try:
            count = await self.__ticket_repo.get_cnt_of_pending_tickets_by_stop(
                stop_id=stop_id,
            )
            return count > 0
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при подсчёте пассажиров на остановке {stop_id}: {e}")
            return False

    async def mark_absent_not_boarded_tickets(
        self,
        *,
        ride_id: uuid.UUID,
        stop_id: uuid.UUID,
    ) -> None:
        """Отметить как отсутствующие все непосаженные билеты."""
        try:
            await self.__ticket_repo.mark_absent_not_boarded_tickets(
                ride_id=ride_id,
                stop_id=stop_id,
            )
            logger.info(f"Отмечены как отсутствующие билеты поездки {ride_id} на остановке {stop_id}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при отметке непосаженных билетов поездки {ride_id}: {e}")
            raise TicketServiceError(f"Не удалось отметить непосаженные билеты: {e}")

    async def __get_first_active_ride(self) -> Ride | None:
        """Получить первую активную поездку."""
        try:
            return await self.__ride_repo.get_by_status(status=RideStatus.IN_PROGRESS)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активной поездки: {e}")
            return None
        except Exception as e:
            logger.error(f"Активная поездка не найдена: {e}")
            return None
