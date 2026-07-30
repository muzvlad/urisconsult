"""
Тесты для SQLiteStorage (FSM хранилище).
"""
import pytest
import asyncio
import os
from unittest.mock import MagicMock

from aiogram.fsm.storage.base import StorageKey


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_fsm.db")


@pytest.fixture
def storage(db_path):
    from services.fsm_storage import SQLiteStorage
    return SQLiteStorage(db_path)


@pytest.fixture
def key():
    return StorageKey(bot_id=1, chat_id=100, user_id=200, thread_id=None)


@pytest.mark.asyncio
async def test_set_get_state(storage, key):
    """Установка и чтение состояния."""
    await storage.set_state(key, "WorkerForm:name")
    state = await storage.get_state(key)
    assert state == "WorkerForm:name"


@pytest.mark.asyncio
async def test_set_state_none(storage, key):
    """Очистка состояния."""
    await storage.set_state(key, "WorkerForm:name")
    await storage.set_state(key, None)
    state = await storage.get_state(key)
    assert state is None


@pytest.mark.asyncio
async def test_set_state_twice_no_duplicates(storage, key):
    """Двойной set_state не создаёт дубли (NULL thread_id)."""
    await storage.set_state(key, "WorkerForm:name")
    await storage.set_state(key, "WorkerForm:citizenship")
    state = await storage.get_state(key)
    assert state == "WorkerForm:citizenship"

    # Проверяем что запись одна
    conn = await storage._get_conn()
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=?",
        (key.bot_id, key.chat_id, key.user_id),
    )
    count = (await cursor.fetchone())[0]
    assert count == 1, f"Expected 1 row, got {count}"


@pytest.mark.asyncio
async def test_set_get_data(storage, key):
    """Установка и чтение данных."""
    await storage.set_data(key, {"name": "Иван", "phone": "+7999"})
    data = await storage.get_data(key)
    assert data["name"] == "Иван"
    assert data["phone"] == "+7999"


@pytest.mark.asyncio
async def test_update_data(storage, key):
    """Обновление данных (не замена)."""
    await storage.set_data(key, {"name": "Иван"})
    await storage.set_data(key, {"phone": "+7999"})
    data = await storage.get_data(key)
    assert data == {"phone": "+7999"}


@pytest.mark.asyncio
async def test_different_users(storage):
    """Разные пользователи — независимые состояния."""
    key1 = StorageKey(bot_id=1, chat_id=100, user_id=111)
    key2 = StorageKey(bot_id=1, chat_id=100, user_id=222)

    await storage.set_state(key1, "WorkerForm:name")
    await storage.set_state(key2, "WorkerForm:citizenship")

    assert await storage.get_state(key1) == "WorkerForm:name"
    assert await storage.get_state(key2) == "WorkerForm:citizenship"


@pytest.mark.asyncio
async def test_get_state_empty(storage, key):
    """Пустое хранилище — None."""
    state = await storage.get_state(key)
    assert state is None


@pytest.mark.asyncio
async def test_get_data_empty(storage, key):
    """Пустое хранилище — пустой dict."""
    data = await storage.get_data(key)
    assert data == {}


@pytest.mark.asyncio
async def test_full_flow(storage, key):
    """Полный сценарий: /start → ФИО → категория → ..."""
    # /start: clear + set_state(name)
    await storage.set_state(key, None)
    await storage.set_state(key, "WorkerForm:name")

    # Пользователь отправил ФИО
    await storage.set_data(key, {"name": "Иванов Иван"})
    await storage.set_state(key, "WorkerForm:citizenship")

    # Проверяем
    assert await storage.get_state(key) == "WorkerForm:citizenship"
    data = await storage.get_data(key)
    assert data["name"] == "Иванов Иван"


@pytest.mark.asyncio
async def test_close(storage):
    """Закрытие соединения."""
    await storage._get_conn()
    await storage.close()
    assert storage._conn is None
