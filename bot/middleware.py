"""
Middleware для ограничения частоты запросов (anti-spam).
"""
import time
import logging
import asyncio
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Ограничивает частоту сообщений от одного пользователя.

    По умолчанию: максимум 5 сообщений в 10 секунд.
    Периодическая очистка неактивных пользователей (каждые 60 сек).
    """

    def __init__(self, rate_limit: int = 5, period: float = 10.0):
        """
        Args:
            rate_limit: максимальное количество сообщений за period
            period: временной интервал в секундах
        """
        super().__init__()
        self.rate_limit = rate_limit
        self.period = period
        self.user_timestamps: dict[int, list[float]] = defaultdict(list)
        self._cleanup_task: asyncio.Task | None = None

    async def _periodic_cleanup(self):
        """Фоновая задача: очистка неактивных пользователей каждые 60 сек."""
        while True:
            await asyncio.sleep(60)
            now = time.time()
            inactive_keys = [
                uid for uid, ts in self.user_timestamps.items()
                if not ts or all(now - t >= self.period for t in ts)
            ]
            for uid in inactive_keys:
                del self.user_timestamps[uid]
            if inactive_keys:
                logger.debug("Очищено %d неактивных пользователей из rate-limit кэша",
                             len(inactive_keys))

    async def __call__(self, handler, event: Message, data: dict):
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        # Запускаем фоновую очистку при первом запросе
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        now = time.time()
        timestamps = self.user_timestamps[user_id]

        # Удаляем старые метки
        timestamps = [t for t in timestamps if now - t < self.period]
        self.user_timestamps[user_id] = timestamps

        if len(timestamps) >= self.rate_limit:
            logger.warning("Rate limit exceeded для user %d", user_id)
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Слишком много сообщений. Подождите немного."
                )
            return None

        timestamps.append(now)
        return await handler(event, data)
