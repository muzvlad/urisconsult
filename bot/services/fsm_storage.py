"""
SQLite-хранилище для FSM aiogram.
Позволяет восстанавливать состояние диалога после перезапуска бота.
"""
import json
import logging
from typing import Any, Mapping, Optional

import aiosqlite
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS fsm_storage (
    bot_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    thread_id INTEGER,
    state TEXT,
    data TEXT,
    PRIMARY KEY (bot_id, chat_id, user_id, thread_id)
)
"""


class SQLiteStorage(BaseStorage):
    """Хранилище FSM в SQLite — выживает при перезапуске бота."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._db_path)
            await self._conn.execute(_CREATE_TABLE)
            await self._conn.commit()
        return self._conn

    async def set_state(self, key: StorageKey, state: State = None) -> None:
        conn = await self._get_conn()
        state_str = state.state if state and hasattr(state, 'state') else (str(state) if state else None)
        await conn.execute(
            """INSERT INTO fsm_storage (bot_id, chat_id, user_id, thread_id, state)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(bot_id, chat_id, user_id, thread_id)
               DO UPDATE SET state = excluded.state""",
            (key.bot_id, key.chat_id, key.user_id, key.thread_id, state_str),
        )
        await conn.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT state FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=? AND thread_id IS ?",
            (key.bot_id, key.chat_id, key.user_id, key.thread_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        conn = await self._get_conn()
        data_json = json.dumps(dict(data), ensure_ascii=False)
        await conn.execute(
            """INSERT INTO fsm_storage (bot_id, chat_id, user_id, thread_id, data)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(bot_id, chat_id, user_id, thread_id)
               DO UPDATE SET data = excluded.data""",
            (key.bot_id, key.chat_id, key.user_id, key.thread_id, data_json),
        )
        await conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT data FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=? AND thread_id IS ?",
            (key.bot_id, key.chat_id, key.user_id, key.thread_id),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
