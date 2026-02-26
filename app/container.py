from aiogram import Bot
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dependency_injector import containers, providers

from app.bot.adapter import TelegramBotAdapter
from app.repositories.ride import RideRepository
from app.repositories.stop import StopRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository
from app.services.location import LocationService
from app.services.ride import RideService
from app.services.timer import TimerService
from app.settings import settings


class Container(containers.DeclarativeContainer):

    config = providers.Configuration()

    redis = providers.Singleton(
        Redis,
        host=config.redis_host,
        port=config.redis_port,
        decode_responses=True
    )

    engine = providers.Singleton(
        create_async_engine,
        config.database_url,
        pool_size=20,
        max_overflow=10,
        echo=False,
    )

    async_session_maker = providers.Singleton(
        async_sessionmaker,
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession
    )

    session = providers.Resource(
        lambda factory: factory(),
        factory=async_session_maker
    )

    bot = providers.Singleton(
        Bot,
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    bot_port = providers.Singleton(
        TelegramBotAdapter,
        bot=bot
    )

    user_repo = providers.Singleton(
        UserRepository,
        session=session
    )
    
    ticket_repo = providers.Singleton(
        TicketRepository,
        session=session
    )
    
    ride_repo = providers.Singleton(
        RideRepository,
        session=session
    )
    
    stop_repo = providers.Singleton(
        StopRepository,
        session=session
    )

    location_service = providers.Singleton(
        LocationService
    )
    
    timer_service = providers.Singleton(
        TimerService,
        redis=redis
    )

    ride_service = providers.Singleton(
        RideService,
        bot_port=bot_port,
        user_repo=user_repo,
        ride_repo=ride_repo,
        stop_repo=stop_repo,
        ticket_repo=ticket_repo,
        location_service=location_service,
        timer_service=timer_service,
        redis=redis
    )
    
    

    



        

