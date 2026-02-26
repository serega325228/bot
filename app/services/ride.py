from time import time
import uuid
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

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

logger = logging.getLogger(__name__)


class RideServiceError(Exception):
    """Базовое исключение для RideService."""
    pass


class RideNotFoundError(RideServiceError):
    """Поездка не найдена."""
    pass


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
        try:
            ride = Ride(
                driver_id=driver_id,
                next_stop_id=next_stop_id,
            )
            result = await self.__ride_repo.create(ride=ride)
            logger.info(f"Поездка {result.id} начата водителем {driver_id}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании поездки для водителя {driver_id}: {e}")
            raise RideServiceError(f"Не удалось создать поездку: {e}")

    async def get_first_active_ride(self) -> Ride | None:
        """Получить первую активную поездку."""
        try:
            return await self.__ride_repo.get_by_status(status=RideStatus.IN_PROGRESS)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активной поездки: {e}")
            return None
        except Exception as e:
            logger.error(f"Активная поездка не найдена: {e}")
            return None

    async def get_active_ride(self, *, driver_id: int) -> Ride | None:
        """Получить активную поездку водителя."""
        try:
            return await self.__ride_repo.get_ride_by_driver(driver_id=driver_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении поездки водителя {driver_id}: {e}")
            return None

    async def restore_ride_timers(self) -> None:
        """Восстановить таймеры поездок после рестарта бота."""
        try:
            await self.__timer_service.restore_all_timers()
            logger.info("Таймеры поездок восстановлены")
        except Exception as e:
            logger.error(f"Ошибка при восстановлении таймеров: {e}")

    async def process_driver_location(
        self,
        *,
        location,
        driver_id: int,
    ) -> uuid.UUID | None:
        """Обработать геолокацию водителя."""
        try:
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

            if not stop or not ride:
                return

            stop = await self.__location_service.find_stop_in_radius(
                stop=stop,
                latitude=lat,
                longitude=lon,
            )

            if stop:
                await self.arrive_at_stop(ride=ride, stop=stop)
                return stop.id

        except RedisError as e:
            logger.error(f"Ошибка Redis при обработке геолокации водителя {driver_id}: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при обработке геолокации водителя {driver_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке геолокации водителя {driver_id}: {e}")

        return None

    async def arrive_at_stop(
        self,
        *,
        ride: Ride,
        stop: Stop,
    ) -> None:
        """Прибыть на остановку."""
        try:
            if ride.timer_started:
                logger.debug(f"Таймер уже запущен для поездки {ride.id}")
                return

            next_stop = await self.__stop_service.get_stop_by_order(order=stop.order + 1)
            if not next_stop:
                logger.warning(f"Следующая остановка не найдена для порядка {stop.order + 1}")
                return

            await self.__ride_repo.update_ride_stops(
                ride_id=ride.id,
                current_stop_id=stop.id,
                next_stop_id=next_stop.id,
            )

            if not await self.__ticket_service.has_waiting_passengers(stop_id=stop.id):
                logger.debug(f"Нет ожидающих пассажиров на остановке {stop.id}")
                return

            await self._schedule_ride_timer(
                ride=ride,
                stop=stop,
                duration=settings.WAIT_TIMER_SECONDS,
            )
            logger.info(f"Поездка {ride.id} прибыла на остановку {stop.name}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при прибытии на остановку {stop.id}: {e}")
            raise RideServiceError(f"Не удалось прибыть на остановку: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при прибытии на остановку {stop.id}: {e}")
            raise RideServiceError(f"Ошибка при прибытии на остановку: {e}")

    async def on_wait_timer_expired(
        self,
        *,
        ride: Ride,
        stop: Stop,
        **_,
    ) -> None:
        """Обработчик истечения таймера ожидания."""
        try:
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
            logger.info(f"Таймер ожидания истёк для поездки {ride.id}")
        except Exception as e:
            logger.error(f"Ошибка при истечении таймера ожидания поездки {ride.id}: {e}")

    async def on_grace_timer_expired(
        self,
        *,
        ride: Ride,
        stop: Stop,
        **_,
    ) -> None:
        """Обработчик истечения grace таймера."""
        try:
            await self.__ticket_service.mark_absent_not_boarded_tickets(
                ride_id=ride.id,
                stop_id=stop.id,
            )

            ride.current_stop_id = None
            ride.timer_started = False

            await self.__ride_repo.save(ride=ride)
            logger.info(f"Grace таймер истёк для поездки {ride.id}, остановка {stop.name} завершена")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при завершении остановки {stop.id} поездки {ride.id}: {e}")
            raise RideServiceError(f"Не удалось завершить остановку: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при завершении остановки {stop.id}: {e}")
            raise RideServiceError(f"Ошибка при завершении остановки: {e}")

    async def on_wait_tick(
        self,
        remaining: int,
        *,
        timer_messages: dict[int, int],
        **_,
    ) -> None:
        """Обработчик тика таймера ожидания."""
        try:
            text = self._build_timer_text(remaining)

            for chat_id, message_id in timer_messages.items():
                try:
                    await self.__bot.edit_timer(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                    )
                except Exception as e:
                    logger.warning(f"Не удалось обновить таймер для чата {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении таймера: {e}")

    async def _schedule_ride_timer(
        self,
        *,
        ride: Ride,
        stop: Stop,
        duration: int,
    ) -> None:
        """Запланировать таймер поездки."""
        try:
            chat_ids = await self.__get_chat_ids_by_ride(ride_id=ride.id)

            timer_messages = {}

            for chat_id in chat_ids:
                try:
                    msg = await self.__bot.send_timer_message(
                        chat_id=chat_id,
                        text=self._build_timer_text(duration),
                    )
                    timer_messages[chat_id] = msg.message_id
                except Exception as e:
                    logger.warning(f"Не удалось отправить таймер в чат {chat_id}: {e}")

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
            logger.info(f"Таймер запланирован для поездки {ride.id} на {duration} сек")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при планировании таймера поездки {ride.id}: {e}")
            raise RideServiceError(f"Не удалось запланировать таймер: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при планировании таймера поездки {ride.id}: {e}")
            raise RideServiceError(f"Ошибка при планировании таймера: {e}")

    def _build_timer_text(self, remaining: int) -> str:
        """Построить текст таймера."""
        return f"⏳ Осталось {remaining} сек"

    async def __get_chat_ids_by_ride(self, *, ride_id: uuid.UUID) -> list[int]:
        """Получить chat_id пользователей поездки."""
        try:
            users = await self.__ride_repo.get_users_by_ride(ride_id=ride_id)
            return [u.id for u in users]
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователей поездки {ride_id}: {e}")
            return []

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
