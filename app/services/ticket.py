import uuid

from app.models.ticket import Ticket, TicketStatus
from app.models.ride import Ride, RideStatus
from app.repositories.ticket import TicketRepository
from app.repositories.ride import RideRepository


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
        return await self.__ticket_repo.get_active_ticket(user_id=user_id)

    async def get_ticket_by_id(self, *, ticket_id: uuid.UUID) -> Ticket | None:
        """Получить билет по ID."""
        return await self.__ticket_repo.get_by_id(ticket_id=ticket_id)

    async def create_or_update_ticket(
        self,
        *,
        stop_id: uuid.UUID,
        user_id: int,
        status: TicketStatus = TicketStatus.PENDING,
    ) -> None:
        """Создать или обновить билет."""
        ticket = await self.get_active_ticket(user_id=user_id)

        if not ticket:
            ride = await self.__get_first_active_ride()
            ticket = Ticket(
                ride_id=ride.id,
                stop_id=stop_id,
                user_id=user_id,
                status=status,
            )
            await self.__ticket_repo.create(ticket=ticket)
        else:
            await self.__ticket_repo.update_ticket_stop(
                ticket_id=ticket.id,
                stop_id=stop_id,
            )

    async def mark_as_boarded(self, *, ticket_id: uuid.UUID) -> None:
        """Отметить билет как посаженный."""
        await self.__ticket_repo.change_status(
            ticket_id=ticket_id,
            status=TicketStatus.BOARDED,
        )

    async def mark_as_absent(self, *, ticket_id: uuid.UUID) -> None:
        """Отметить билет как отсутствующий."""
        await self.__ticket_repo.change_status(
            ticket_id=ticket_id,
            status=TicketStatus.ABSENT,
        )

    async def has_waiting_passengers(self, *, stop_id: uuid.UUID) -> bool:
        """Проверить, есть ли ожидающие пассажиры на остановке."""
        count = await self.__ticket_repo.get_cnt_of_pending_tickets_by_stop(
            stop_id=stop_id,
        )
        return count > 0

    async def mark_absent_not_boarded_tickets(
        self,
        *,
        ride_id: uuid.UUID,
        stop_id: uuid.UUID,
    ) -> None:
        """Отметить как отсутствующие все непосаженные билеты."""
        await self.__ticket_repo.mark_absent_not_boarded_tickets(
            ride_id=ride_id,
            stop_id=stop_id,
        )

    async def __get_first_active_ride(self) -> Ride:
        """Получить первую активную поездку."""
        return await self.__ride_repo.get_by_status(status=RideStatus.IN_PROGRESS)
