import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride, RideStatus
from app.models.user import User
from app.models.ticket import Ticket

class RideRepository:
    def __init__(self, *, session: AsyncSession):
        self.__session = session

    async def create(self, *, ride: Ride):
        self.__session.add(ride)
        await self.__session.commit()

        return ride
    
    async def get_by_id(self, *, id: uuid.UUID):
        query = select(Ride).filter_by(id=id)

        result = await self.__session.execute(query)

        return result.scalar_one_or_none()
    
    async def get_by_status(self, *, status: RideStatus, limit: int = 1):
        query = select(Ride).filter_by(status=status).limit(limit)

        result = await self.__session.execute(query)

        return result.scalar_one()

    async def save(self, *, ride: Ride):
        self.__session.add(ride)

        await self.__session.flush()

    async def change_timer_state(self, *, id: uuid.UUID, state: bool):
        query = update(Ride).filter_by(id=id).values(timer_started=state)

        await self.__session.execute(query)
    
    async def get_ride_by_driver(self, *, driver_id: int):
        query = select(Ride).filter_by(driver_id=driver_id)

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def update_ride_stops(
        self,
        *,
        ride_id: uuid.UUID,
        current_stop_id: uuid.UUID,
        next_stop_id: uuid.UUID
    ):
        query = (
            update(Ride)
            .filter_by(id=ride_id)
            .values(
                current_stop_id=current_stop_id,
                next_stop_id=next_stop_id
            )
            .returning()
        )

        result = await self.__session.execute(query)

        return result.scalar_one()

    async def get_users_by_ride(self, *, ride_id: uuid.UUID) -> list[User]:
        """Получить пользователей поездки."""
        query = (
            select(User)
            .join(Ticket, Ticket.user_id == User.id)
            .filter_by(ride_id=ride_id)
        )
        result = await self.__session.execute(query)
        return list(result.scalars().all())