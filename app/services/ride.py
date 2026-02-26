from time import time
import uuid

from redis.asyncio import Redis

from app.bot.port import BotPort
from app.models.ride import Ride, RideStatus
from app.models.stop import Stop
from app.services.location import LocationService
from app.services.timer import TimerService
from app.services.ticket import TicketService
from app.services.stop import StopService
from app.repositories.ride import RideRepository
from app.repositories.stop import StopRepository
from app.settings import settings


class RideService:
    """Сервис для управления поездками."""

    def __init__(
        self,
        *,
        ride_repo: RideRepository,
        stop_repo: StopRepository,
        location_service: LocationService,
        timer_service: TimerService,
        ticket_service: TicketService,
        stop_service: StopService,
        bot_port: BotPort,
        redis: Redis,
    ):
        self.__ride_repo = ride_repo
        self.__stop_repo = stop_repo
        self.__location_service = location_service
        self.__timer_service = timer_service
        self.__ticket_service = ticket_service
        self.__stop_service = stop_service
        self.__bot = bot_port
        self.__redis = redis

    # ========== Основная логика поездок ==========

    async def start_ride(self, *, driver_id: int, next_stop_id: uuid.UUID) -> Ride:
        """Начать новую поездку."""
        ride = Ride(
            driver_id=driver_id,
            next_stop_id=next_stop_id,
        )
        return await self.__ride_repo.create(ride=ride)

    async def get_first_active_ride(self) -> Ride:
        """Получить первую активную поездку."""
        return await self.__ride_repo.get_by_status(status=RideStatus.IN_PROGRESS)

    async def get_active_ride(self, *, driver_id: int) -> Ride | None:
        """Получить активную поездку водителя."""
        return await self.__ride_repo.get_ride_by_driver(driver_id=driver_id)

    async def restore_ride_timers(self) -> None:
        """Восстановить таймеры поездок после рестарта бота."""
        await self.__timer_service.restore_all_timers()

    async def process_driver_location(
        self,
        *,
        location,
        driver_id: int,
    ) -> uuid.UUID | None:
        """Обработать геолокацию водителя."""
        lat = location.latitude
        lon = location.longitude

        is_live = location.live_period is not None

        if not is_live:
            return

        now = time.time()

        last = await self.__redis.get(f"last_gps:{driver_id}")

        if last and now - float(last) < settings.GPS_DEBOUNCE_SECONDS:
            return

        await self.__redis.set(
            f"last_gps:{driver_id}",
            now,
            ex=10,
        )

        stop, ride = await self.__stop_repo.get_stop_n_ride_by_driver(
            driver_id=driver_id,
        )

        stop = await self.__location_service.find_stop_in_radius(
            stop=stop,
            latitude=lat,
            longitude=lon,
        )

        if stop:
            await self.arrive_at_stop(ride=ride, stop=stop)

    async def arrive_at_stop(
        self,
        *,
        ride: Ride,
        stop: Stop,
    ) -> None:
        """Прибыть на остановку."""
        if ride.timer_started:
            return

        next_stop = await self.__stop_repo.get_by_order(order=stop.order + 1)

        await self.__ride_repo.update_ride_stops(
            ride_id=ride.id,
            current_stop_id=stop.id,
            next_stop_id=next_stop.id,
        )

        if not await self.__ticket_service.has_waiting_passengers(stop_id=stop.id):
            return

        await self._schedule_ride_timer(
            ride=ride,
            stop=stop,
            duration=settings.WAIT_TIMER_SECONDS,
        )

    async def on_wait_timer_expired(
        self,
        *,
        ride: Ride,
        stop: Stop,
        **_,
    ) -> None:
        """Обработчик истечения таймера ожидания."""
        self.__timer_service.start_timer(
            timer_id=ride.id,
            timer_type="grace",
            duration=settings.BOARDED_GRACE_SECONDS,
            on_expired=self.on_grace_timer_expired,
            payload={
                "ride": ride,
                "stop": stop,
                "_on_expired": self.on_grace_timer_expired,
            },
        )

    async def on_grace_timer_expired(
        self,
        *,
        ride: Ride,
        stop: Stop,
        **_,
    ) -> None:
        """Обработчик истечения grace таймера."""
        await self.__ticket_service.mark_absent_not_boarded_tickets(
            ride_id=ride.id,
            stop_id=stop.id,
        )

        ride.current_stop_id = None
        ride.timer_started = False

        await self.__ride_repo.save(ride=ride)

    async def on_wait_tick(
        self,
        remaining: int,
        *,
        timer_messages: dict[int, int],
        **_,
    ) -> None:
        """Обработчик тика таймера ожидания."""
        text = self._build_timer_text(remaining)

        for chat_id, message_id in timer_messages.items():
            await self.__bot.edit_timer(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )

    async def _schedule_ride_timer(
        self,
        *,
        ride: Ride,
        stop: Stop,
        duration: int,
    ) -> None:
        """Запланировать таймер поездки."""
        chat_ids = await self.__get_chat_ids_by_ride(ride_id=ride.id)

        timer_messages = {}

        for chat_id in chat_ids:
            msg = await self.__bot.send_timer_message(
                chat_id=chat_id,
                text=self._build_timer_text(duration),
            )
            timer_messages[chat_id] = msg.message_id

        self.__timer_service.start_timer(
            timer_id=ride.id,
            timer_type="wait",
            duration=duration,
            on_tick=self.on_wait_tick,
            on_expired=self.on_wait_timer_expired,
            payload={
                "ride": ride,
                "stop": stop,
                "timer_messages": timer_messages,
                "_on_expired": self.on_wait_timer_expired,
            },
        )

        ride.timer_started = True
        await self.__ride_repo.save(ride=ride)

    def _build_timer_text(self, remaining: int) -> str:
        """Построить текст таймера."""
        return f"⏳ Осталось {remaining} сек"

    async def __get_chat_ids_by_ride(self, *, ride_id: uuid.UUID) -> list[int]:
        """Получить chat_id пользователей поездки."""
        users = await self.__ride_repo.get_users_by_ride(ride_id=ride_id)
        return [u.id for u in users]

    # ========== Делегирование в StopService (для хендлеров) ==========

    async def get_active_stops(self):
        return await self.__stop_service.get_active_stops()

    async def get_stop_by_id(self, *, stop_id: uuid.UUID):
        return await self.__stop_service.get_stop_by_id(stop_id=stop_id)

    # ========== Делегирование в TicketService (для хендлеров) ==========

    async def get_active_ticket(self, *, user_id: int):
        return await self.__ticket_service.get_active_ticket(user_id=user_id)

    async def create_or_update_ticket(self, *, stop_id: uuid.UUID, user_id: int, status):
        await self.__ticket_service.create_or_update_ticket(
            stop_id=stop_id,
            user_id=user_id,
            status=status,
        )

    async def mark_as_boarded(self, *, ticket_id: uuid.UUID):
        await self.__ticket_service.mark_as_boarded(ticket_id=ticket_id)

    async def mark_as_absent(self, *, ticket_id: uuid.UUID):
        await self.__ticket_service.mark_as_absent(ticket_id=ticket_id)
