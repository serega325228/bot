from time import time
import uuid

from redis.asyncio import Redis

from app.bot.port import BotPort
from app.models.ride import Ride, RideStatus
from app.models.stop import Stop
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, UserRole
from app.repositories.ride import RideRepository
from app.repositories.stop import StopRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository
from app.services.location import LocationService
from app.services.timer import TimerService
from app.settings import settings

class RideService:
    def __init__(
        self,
        *,
        ride_repo: RideRepository,
        stop_repo: StopRepository,
        user_repo: UserRepository,
        ticket_repo: TicketRepository,
        location_service: LocationService,
        timer_service: TimerService,
        bot_port: BotPort,
        redis: Redis
    ):
        self.__ride_repo = ride_repo
        self.__stop_repo = stop_repo
        self.__user_repo = user_repo
        self.__ticket_repo = ticket_repo
        self.__location_service = location_service
        self.__timer_service = timer_service
        self.__bot = bot_port
        self.__redis = redis
        #self.__LAST_GPS = {}

    async def start_ride(self, *, driver_id: int, next_stop_id: uuid.UUID):
        ride = Ride(
            driver_id=driver_id,
            next_stop_id=next_stop_id
        )

        return await self.__ride_repo.create(ride=ride)
    
    async def get_first_active_ride(self):
        return await self.__ride_repo.get_by_status(status=RideStatus.IN_PROGRESS)

    async def get_active_ride(self, *, driver_id: int):
        return await self.__ride_repo.get_ride_by_driver(driver_id=driver_id)
    
    async def restore_ride_timers(self):
        keys = await self.__redis.keys("timer:ride:*")

        for key in keys:
            ride_id = uuid.UUID(key.split(":")[-1])
            end_at = int(await self.__redis.get(key))

            ride = await self.__ride_repo.get_by_id(id=ride_id)
            stop = await self.__stop_repo.get_by_id(id=ride.current_stop_id)

            await self._schedule_ride_timer(
                ride=ride,
                stop=stop,
                duration=end_at-int(time.time())
            )

    async def process_driver_location(
        self,
        *,
        location,
        driver_id: int,
    ) -> uuid.UUID | None:
        
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
            ex=10
        )

        stop, ride = await self.__stop_repo.get_stop_n_ride_by_driver(driver_id=driver_id)

        stop = await self.__location_service.find_stop_in_radius(
            stop=stop,
            latitude=lat,
            longitude=lon
        )

        if stop:
            await self.arrive_at_stop(
                ride=ride,
                stop=stop
            )
 
    async def arrive_at_stop(
        self,
        *,
        ride: Ride,
        stop: Stop
    ):
        if ride.timer_started:
            return

        next_stop = await self._calculate_next_stop(stop=stop)

        await self.__ride_repo.update_ride_stops(
            ride_id=ride.id, 
            current_stop_id=stop.id,
            next_stop_id=next_stop.id
        )

        if not await self.has_waiting_passengers(stop_id=stop.id):
            return
        
        await self._schedule_ride_timer(
            ride=ride, 
            stop=stop,
            duration=settings.WAIT_TIMER_SECONDS
        )

    async def on_wait_timer_expired(
        self, 
        *, 
        ride: Ride, 
        stop: Stop,
        **_
    ):
        self.__timer_service.start_timer(
            timer_id=ride.id,
            duration=settings.BOARDED_GRACE_SECONDS,
            on_expired=self.on_grace_timer_expired,
            payload={
                "ride": ride,
                "stop": stop
            }
        )

    async def on_grace_timer_expired(
        self, 
        *, 
        ride: Ride,
        stop: Stop,
        **_
    ):
        await self.finalize_stop(
            ride=ride,
            stop=stop
        )

    async def on_wait_tick(
        self,
        remaining: int,
        *,
        timer_messages: dict[int, int],
        **_
    ):
        text = self._build_timer_text(remaining)

        for chat_id, message_id in timer_messages.items():
            await self.__bot.edit_timer(
                chat_id=chat_id,
                message_id=message_id,
                text=text
            )

    async def _schedule_ride_timer(
        self, 
        *, 
        ride: Ride, 
        stop: Stop, 
        duration: int
    ):
        chat_ids = await self.chat_ids_by_ride(ride_id=ride.id)

        timer_messages = {}

        for chat_id in chat_ids:
            msg = await self.__bot.send_timer_message(
                chat_id=chat_id,
                text=self._build_timer_text(duration)
            )
            timer_messages[chat_id] = msg.message_id

        self.__timer_service.start_timer(
            timer_id=ride.id,
            duration=duration,
            on_expired=self.on_wait_timer_expired,
            on_tick=self.on_wait_tick,
            payload={
                "ride": ride,
                "stop": stop,
                "timer_messages": timer_messages
            }
        )

        if not await self.__redis.get(f"timer:ride:{ride.id}"):

            end_at = int(time.time()) + duration

            await self.__redis.set(
                f"timer:ride:{ride.id}",
                end_at
            )

        ride.timer_started = True
        await self.__ride_repo.save(ride=ride)

    def _build_timer_text(self, remaining: int):
        return f"⏳ Осталось {remaining} сек"

    async def _calculate_next_stop(self, *, stop: Stop):
        return await self.__stop_repo.get_by_order(order=stop.order+1)
    
    async def create_stop(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        order: int,
    ):
        stop = Stop(
            name=name,
            latitude=latitude,
            longitude=longitude,
            order=order
        )

        await self.__stop_repo.create(stop=stop)

    async def deactivate_stop(self, *, id: uuid.UUID):
        stop = await self.get_stop_by_id(stop_id=id)
        if stop and stop.is_active:
            stop.is_active = False
            await self.__stop_repo.save(stop=stop)

    async def activate_stop(self, *, id: uuid.UUID):
        stop = await self.get_stop_by_id(stop_id=id)
        if stop and not stop.is_active:
            stop.is_active = True
            await self.__stop_repo.save(stop=stop)    

    async def delete_stop(self, *, id: uuid.UUID):
        await self.__stop_repo.delete(id=id)

    async def get_active_stops(self):
        return await self.__stop_repo.get_active()
    
    async def get_stop_by_name(self, *, name: str):
        return await self.__stop_repo.get_by_name(name=name)
    
    async def get_all_stops(self):
        return await self.__stop_repo.get_all()

    async def get_stop_by_id(self, *, stop_id: uuid.UUID):
        return await self.__stop_repo.get_by_id(id=stop_id)

    async def create_or_update_ticket(
            self, 
            *, 
            stop_id: uuid.UUID, 
            user_id: int, 
            status: TicketStatus = TicketStatus.PENDING,
        ):

        ticket = await self.__ticket_repo.get_active_ticket(user_id=user_id)

        if not ticket:

            ride = await self.get_first_active_ride()

            ticket = Ticket(
                ride_id=ride.id,
                stop_id=stop_id,
                user_id=user_id,
                status=status
            )

            await self.__ticket_repo.create(ticket=ticket)

        else:
            await self.__ticket_repo.update_ticket_stop(
                ticket_id=ticket.id,
                stop_id=stop_id
            )

    async def mark_as_boarded(self, *, ticket_id: uuid.UUID):
        return await self.__ticket_repo.change_status(ticket_id=ticket_id, status=TicketStatus.BOARDED)
    
    async def mark_as_absent(self, *, ticket_id: uuid.UUID):
        return await self.__ticket_repo.change_status(ticket_id=ticket_id, status=TicketStatus.ABSENT)

    async def has_waiting_passengers(self, *, stop_id: uuid.UUID):
        return await self.__ticket_repo.get_cnt_of_pending_tickets_by_stop(stop_id=stop_id) > 0

    async def finalize_stop(self, *, ride: Ride, stop: Stop):
        await self.__ticket_repo.mark_absent_not_boarded_tickets(
            ride_id=ride.id,
            stop_id=stop.id
        )

        ride.current_stop_id = None
        ride.timer_started = False

        await self.__ride_repo.save(ride=ride)

    async def get_active_ticket(self, *, user_id: int):
        return await self.__ticket_repo.get_active_ticket(user_id=user_id)

    async def create_user(
            self, 
            *, 
            id: int,
            full_name: str, 
            role: UserRole = UserRole.PASSENGER, 
            nickname: str = ""
        ):
        if await self.get_user_by_id(id=id):
            raise Exception("User already exist")
        
        user = User(
            id=id,
            full_name=full_name,
            nickname=nickname,
            role=role,
            is_active=True,
        )

        await self.__user_repo.create(user=user)

    async def activate_user(self, *, id: int):
        user = await self.get_user_by_id(id=id)

        if user and not user.is_active:
            user.is_active = True
            await self.__user_repo.save(user=user)

    async def deactivate_user(self, *, id: int):
        user = await self.get_user_by_id(id=id)

        if user and user.is_active:
            user.is_active = False
            await self.__user_repo.save(user=user)

    async def delete_user(self, *, id: int):
        await self.__user_repo.delete(id=id)

    async def chat_ids_by_ride(self, *, ride_id: uuid.UUID):
        users = await self.__user_repo.get_users_by_ride(ride_id=ride_id)
        return [u.id for u in users]
    
    async def get_user_by_id(self, *, id: int):
        return await self.__user_repo.get_by_id(id=id)
    
    async def get_all_users(self):
        return await self.__user_repo.get_all()
    
    async def make_passenger(self, *, id: int):
        await self.__user_repo.change_role(id=id, role=UserRole.PASSENGER)

    async def make_admin(self, *, id: int):
        await self.__user_repo.change_role(id=id, role=UserRole.ADMIN)

    async def make_driver(self, *, id: int):
        await self.__user_repo.change_role(id=id, role=UserRole.DRIVER)

    async def change_nickname(self, *, id: int, nickname: str):
        await self.__user_repo.change_nickname(id=id, nickname=nickname)

    async def change_full_name(self, *, id: int, full_name: str):
        await self.__user_repo.change_full_name(id=id, full_name=full_name)