import asyncio
import json
import time
import uuid
from typing import Callable, Any

from redis.asyncio import Redis


class TimerService:
    """
    Сервис таймеров с персистентностью в Redis.
    
    Таймеры сохраняются в Redis и восстанавливаются после рестарта бота.
    """

    def __init__(self, redis: Redis):
        self.__redis = redis
        self.__active_timers: dict[uuid.UUID, asyncio.Task] = {}

    async def start_timer(
        self,
        *,
        timer_id: uuid.UUID,
        timer_type: str,
        duration: int,
        on_tick: Callable | None = None,
        on_expired: Callable,
        payload: dict[str, Any]
    ) -> None:
        """
        Запускает таймер с сохранением метаданных в Redis.
        
        Args:
            timer_id: Уникальный ID таймера
            timer_type: Тип таймера ("wait" или "grace")
            duration: Длительность в секундах
            on_tick: Callback для каждого тика (remaining, **payload)
            on_expired: Callback по истечении (**payload)
            payload: Данные для передачи в callback-и
        """
        # Если таймер уже запущен — не создаём дубликат
        if timer_id in self.__active_timers:
            return

        # Сохраняем метаданные в Redis
        await self.__save_timer_state(
            timer_id=timer_id,
            timer_type=timer_type,
            duration=duration,
            payload=payload
        )

        # Создаём задачу в памяти
        task = asyncio.create_task(
            self._run(
                timer_id=timer_id,
                duration=duration,
                on_tick=on_tick,
                on_expired=on_expired,
                payload=payload
            )
        )
        self.__active_timers[timer_id] = task

    async def stop_timer(self, *, timer_id: uuid.UUID) -> None:
        """Останавливает таймер и удаляет из Redis."""
        if timer_id in self.__active_timers:
            self.__active_timers[timer_id].cancel()
            del self.__active_timers[timer_id]

        await self.__redis.delete(f"timer:{timer_id}")

    async def restore_all_timers(self) -> None:
        """
        Восстанавливает все таймеры после рестарта бота.
        Вызывать при старте приложения.
        """
        async for key in self.__redis.scan_iter("timer:*"):
            timer_id = uuid.UUID(key.split(":")[-1])
            data = await self.__load_timer_state(timer_id)

            if not data:
                continue

            remaining = data["end_at"] - int(time.time())

            if remaining <= 0:
                # Таймер уже истёк — вызываем on_expired
                await self.__redis.delete(f"timer:{timer_id}")
                await self.__call_expired_safely(data["payload"])
                continue

            # Пересоздаём таймер с оставшимся временем
            # on_tick не восстанавливаем — чтобы не спамить при рестарте
            task = asyncio.create_task(
                self._run(
                    timer_id=timer_id,
                    duration=int(remaining),
                    on_tick=None,
                    on_expired=self._create_restored_expired_handler(data),
                    payload=data["payload"]
                )
            )
            self.__active_timers[timer_id] = task

    async def _run(
        self,
        *,
        timer_id: uuid.UUID,
        duration: int,
        on_tick: Callable | None,
        on_expired: Callable,
        payload: dict[str, Any]
    ) -> None:
        """Основной цикл таймера."""
        try:
            for remaining in range(duration, 0, -1):
                # Проверяем, не отменён ли таймер
                if timer_id not in self.__active_timers:
                    return

                if on_tick:
                    await self.__call_tick_safely(on_tick, remaining, payload)

                await asyncio.sleep(1)

            # Вызываем on_expired
            await self.__call_expired_safely(payload)

        except asyncio.CancelledError:
            # Таймер отменён — не делаем ничего
            pass
        except Exception as e:
            # Ловим все ошибки, чтобы таймер не падал молча
            print(f"[TimerService] Ошибка таймера {timer_id}: {e}")
        finally:
            # Очищаем состояние
            self.__active_timers.pop(timer_id, None)
            await self.__redis.delete(f"timer:{timer_id}")

    async def __save_timer_state(
        self,
        *,
        timer_id: uuid.UUID,
        timer_type: str,
        duration: int,
        payload: dict[str, Any]
    ) -> None:
        """Сохраняет метаданные таймера в Redis."""
        data = {
            "type": timer_type,
            "duration": duration,
            "end_at": int(time.time()) + duration,
            "payload": payload
        }

        await self.__redis.set(
            f"timer:{timer_id}",
            json.dumps(data),
            ex=duration + 60  # TTL с запасом в 1 минуту
        )

    async def __load_timer_state(
        self,
        timer_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Загружает метаданные таймера из Redis."""
        data_str = await self.__redis.get(f"timer:{timer_id}")
        if not data_str:
            return None

        return json.loads(data_str)

    def _create_restored_expired_handler(
        self,
        data: dict[str, Any]
    ) -> Callable:
        """
        Создаёт handler для истёкшего таймера после восстановления.
        Нужно потому что on_expired — метод и его нельзя сериализовать.
        """
        async def handler(**payload):
            # Вызываем on_expired из payload — там лежит ссылка на метод
            on_expired = payload.get("_on_expired")
            if on_expired:
                await on_expired(**payload)

        return handler

    async def __call_tick_safely(
        self,
        callback: Callable,
        remaining: int,
        payload: dict[str, Any]
    ) -> None:
        """Безопасный вызов on_tick с обработкой ошибок."""
        try:
            await callback(remaining, **payload)
        except Exception as e:
            print(f"[TimerService] Ошибка on_tick: {e}")

    async def __call_expired_safely(
        self,
        payload: dict[str, Any]
    ) -> None:
        """Безопасный вызов on_expired с обработкой ошибок."""
        try:
            on_expired = payload.get("_on_expired")
            if on_expired:
                await on_expired(**payload)
        except Exception as e:
            print(f"[TimerService] Ошибка on_expired: {e}")
