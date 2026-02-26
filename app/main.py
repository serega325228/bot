import asyncio
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers.admin import router as admin
from app.bot.handlers.passenger import router as passenger
from app.bot.handlers.driver import router as driver
from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.di import DIMiddleware
from app.settings import settings
from app.container import Container

async def main():

    container = Container()

    container.config.database_url.from_value(settings.DATABASE_URL)
    container.config.bot_token.from_value(settings.BOT_TOKEN)
    container.config.redis_host.from_value(settings.REDIS_HOST)
    container.config.redis_port.from_value(settings.REDIS_PORT)

    container.wire(
        modules=[
            "app.bot.handlers.driver",
            "app.bot.handlers.admin",
            "app.bot.handlers.passenger"
        ]
    )

    bot = container.bot()

    storage = RedisStorage.from_url(
        "redis://localhost:6379/0"
    )

    dp = Dispatcher(storage=storage)

    dp.message.outer_middleware(DIMiddleware(container=container))
    dp.callback_query.outer_middleware(DIMiddleware(container=container))

    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())

    dp.include_router(admin)
    dp.include_router(passenger)
    dp.include_router(driver)

    ride_service = await container.ride_service()

    await ride_service.restore_ride_timers()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
