import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.stop import Stop

class StopRepository:
    def __init__(self, *, session: AsyncSession):
        self.__session = session

    async def create(self, *, stop: Stop):
        self.__session.add(stop)
        await self.__session.commit()

    async def save(self, *, stop: Stop):
        self.__session.add(stop)
        await self.__session.flush()

    async def delete(self, *, id: uuid.UUID):
        query = delete(Stop).filter_by(id=id)
        await self.__session.execute(query)

    async def update_name(self, *, id: uuid.UUID, name: str):
        query = update(Stop).filter_by(id=id).values(name=name).returning()

        await self.__session.execute(query)

    async def get_by_order(self, *, order: int):
        query = select(Stop).filter_by(order=order)

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def get_by_name(self, *, name: str):
        query = select(Stop).filter_by(name=name)

        result = await self.__session.execute(query)

        return result.scalar_one_or_none()

    async def get_active(self):
        query = select(Stop).filter_by(is_active=True)

        result = await self.__session.execute(query)
        
        return list(result.scalars().all())
    
    async def get_stop_n_ride_by_driver(self, *, driver_id: int):
        query = (
            select(Stop, Ride)
            .join(Ride, Ride.next_stop_id == Stop.id)
            .filter_by(driver_id=driver_id)
        )

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def get_by_id(self, *, id: uuid.UUID):
        query = select(Stop).filter_by(id=id)

        result = await self.__session.execute(query)

        return result.scalar_one()
    
    async def get_all(self):
        result = await self.__session.execute(select(Stop))

        return list(result.scalars().all())