import asyncio
import uuid
from typing import Callable, Dict

class TimerService:
    def __init__(self):
        self.__active_timers: Dict[uuid.UUID, asyncio.Task] = {}

    def start_timer(
        self, 
        *, 
        timer_id: uuid.UUID, 
        duration: int, 
        on_tick: Callable | None = None,
        on_expired: Callable,
        payload: dict
    ):
        if timer_id in self.__active_timers:
            return

        task = asyncio.create_task(
            self._run(timer_id, duration, on_tick, on_expired, payload)
        )
        self.__active_timers[timer_id] = task

    async def _run(self, timer_id, duration, on_tick, on_expired, payload):
        try:
            for remaining in range(duration, 0, -1):
                if on_tick:
                    await on_tick(remaining, **payload)
                await asyncio.sleep(1)
            await on_expired(**payload)
        finally:
            self.__active_timers.pop(timer_id, None)

