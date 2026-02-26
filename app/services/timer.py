import asyncio
import json
import time
import uuid
import logging
from typing import Callable, Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


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
        try:
            # Если таймер уже запущен — не создаём дубликат
            if timer_id in self.__active_timers:
                logger.debug(f"Таймер {timer_id} уже запущен")
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
            logger.info(f"Таймер {timer_id} ({timer_type}) запущен на {duration} сек")
        except RedisError as e:
            logger.error(f"Ошибка Redis при запуске таймера {timer_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запуске таймера {timer_id}: {e}")

    async def stop_timer(self, *, timer_id: uuid.UUID) -> None:
        """Останавливает таймер и удаляет из Redis."""
        try:
            if timer_id in self.__active_timers:
                self.__active_timers[timer_id].cancel()
                del self.__active_timers[timer_id]

            await self.__redis.delete(f"timer:{timer_id}")
            logger.info(f"Таймер {timer_id} остановлен")
        except RedisError as e:
            logger.error(f"Ошибка Redis при остановке таймера {timer_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при остановке таймера {timer_id}: {e}")

    async def restore_all_timers(self) -> None:
        """
        Восстанавливает все таймеры после рестарта бота.
        Вызывать при старте приложения.
        """
        try:
            count = 0
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
                count += 1

            logger.info(f"Восстановлено {count} таймеров")
        except RedisError as e:
            logger.error(f"Ошибка Redis при восстановлении таймеров: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при восстановлении таймеров: {e}")

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
                    logger.debug(f"Таймер {timer_id} отменён")
                    return

                if on_tick:
                    await self.__call_tick_safely(on_tick, remaining, payload)

                await asyncio.sleep(1)

            # Вызываем on_expired
            await self.__call_expired_safely(payload)

        except asyncio.CancelledError:
            # Таймер отменён — не делаем ничего
            logger.debug(f"Таймер {timer_id} отменён через CancelledError")
        except Exception as e:
            # Ловим все ошибки, чтобы таймер не падал молча
            logger.error(f"Ошибка таймера {timer_id}: {e}")
        finally:
            # Очищаем состояние
            self.__active_timers.pop(timer_id, None)
            try:
                await self.__redis.delete(f"timer:{timer_id}")
            except RedisError as e:
                logger.error(f"Ошибка Redis при удалении таймера {timer_id}: {e}")

    async def __save_timer_state(
        self,
        *,
        timer_id: uuid.UUID,
        timer_type: str,
        duration: int,
        payload: dict[str, Any]
    ) -> None:
        """Сохраняет метаданные таймера в Redis."""
        try:
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
        except RedisError as e:
            logger.error(f"Ошибка Redis при сохранении состояния таймера {timer_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при сохранении состояния таймера {timer_id}: {e}")
            raise

    async def __load_timer_state(
        self,
        timer_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Загружает метаданные таймера из Redis."""
        try:
            data_str = await self.__redis.get(f"timer:{timer_id}")
            if not data_str:
                return None

            return json.loads(data_str)
        except RedisError as e:
            logger.error(f"Ошибка Redis при загрузке состояния таймера {timer_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON таймера {timer_id}: {e}")
            return None

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
            logger.error(f"Ошибка в on_tick (remaining={remaining}): {e}")

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
            logger.error(f"Ошибка в on_expired: {e}")
