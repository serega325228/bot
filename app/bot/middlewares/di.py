from aiogram import BaseMiddleware

from app.container import Container

class DIMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        container: Container
    ):
        self.__container = container

    async def __call__(self, handler, event, data):
        data["ride_service"] = await self.__container.ride_service()

        return await handler(event, data)