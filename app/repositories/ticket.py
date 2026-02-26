import uuid
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ride
from app.models.ride import Ride
from app.models.stop import Stop
from app.models.ticket import Ticket, TicketStatus

class TicketRepository:
    def __init__(self, *, session: AsyncSession):
        self.__session = session

    async def get_by_id(self, *, ticket_id: uuid.UUID) -> Ticket | None:
        """Получить билет по ID."""
        query = select(Ticket).filter_by(id=ticket_id)
        result = await self.__session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, *, ticket: Ticket):
        self.__session.add(ticket)
        await self.__session.commit()

    async def update_status(self, *, id: uuid.UUID, status: TicketStatus):
        query = update(Ticket).filter_by(id=id).values(status=status).returning()

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def mark_absent_not_boarded_tickets(
        self,
        *,
        stop_id: uuid.UUID,
        ride_id: uuid.UUID
    ):
        query = (
            update(Ticket)
            .where(
                Ticket.ride_id == ride_id,
                Ticket.stop_id == stop_id,
                Ticket.status != TicketStatus.BOARDED
            )
            .values(status=TicketStatus.ABSENT)
        )

        await self.__session.execute(query)
    
    async def get_cnt_of_pending_tickets_by_stop(self, *, stop_id: uuid.UUID):
        query = (
            select(func.count(Ticket.id))
            .join(Ride, Ride.id == Ticket.ride_id)
            .where(
                Ride.current_stop == stop_id,
                Ticket.status == TicketStatus.PENDING,
            )
        )
        result = await self.__session.execute(query)
        return result.scalar_one()
    
    async def update_status_by_ride(self, *, ride_id: uuid.UUID):
        query = (
            update(Ticket)
            .where(
                Ticket.ride_id == ride_id,
                Ticket.status == TicketStatus.PENDING
            )
            .values(status=TicketStatus.ABSENT)
        )
        
        await self.__session.execute(query)
    
    async def get_by_ride(self, *, user_id: int, stop_id: uuid.UUID):
        query = (
            select(Ticket)
            .join(Ride, Ride.id == Ticket.ride_id)
            .where(
                Ticket.user_id == user_id,
                Ride.current_stop_id == stop_id
            )
        )

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def get_active_ticket(self, *, user_id: int):
        query = (
            select(Ticket)
            .where(
                Ticket.user_id == user_id,
                Ticket.status == TicketStatus.PENDING
            )
        )

        result = await self.__session.execute(query)

        return result.scalar_one_or_none()

    async def update_ticket_stop(self, *, ticket_id: uuid.UUID, stop_id: uuid.UUID):
        query = (
            update(Ticket)
            .filter_by(ticket_id=ticket_id)
            .values(stop_id=stop_id)
        )

        await self.__session.execute(query)

    async def change_status(self, *, ticket_id: uuid.UUID, status: TicketStatus):
        query = (
            update(Ticket)
            .filter_by(ticket_id=ticket_id)
            .values(status=status)
            .returning()
        )

        result = await self.__session.execute(query)

        return result.scalar_one()