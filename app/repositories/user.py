import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.ticket import Ticket
from app.models.user import User, UserRole

class UserRepository:
    def __init__(self, *, session: AsyncSession):
        self.__session = session

    async def create(self, *, user: User):
        self.__session.add(user)
        await self.__session.commit()

    async def save(self, *, user: User):
        self.__session.add(user)
        await self.__session.flush()

    async def delete(self, *, id):
        query = delete(User).filter_by(id=id)

        await self.__session.execute(query)

    async def get_by_id(self, *, id: int):
        query = select(User).filter_by(id=id)

        result = await self.__session.execute(query)

        return result.scalar_one_or_none()
    
    async def get_users_by_ride(self, *, ride_id: uuid.UUID):
        query = (
            select(User)
            .join(Ticket, Ticket.user_id == User.id)
            .filter_by(ride_id=ride_id)
        )

        result = await self.__session.execute(query)

        return list(result.scalars().all())
    
    async def get_all(self):
        result = await self.__session.execute(select(User))

        return list(result.scalars().all())
    
    async def change_role(self, *, id: int, role: UserRole):
        query = (
            update(User)
            .filter_by(id=id)
            .values(role=role)
        )

        await self.__session.execute(query)

    async def change_nickname(self, *, id: int, nickname: str):
        query = (
            update(User)
            .filter_by(id=id)
            .values(nickname=nickname)
        )

        await self.__session.execute(query)

    async def change_full_name(self, *, id: int, full_name: str):
        query = (
            update(User)
            .filter_by(id=id)
            .values(full_name=full_name)
        )

        await self.__session.execute(query)