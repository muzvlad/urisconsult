"""
Тесты для bot/services/db_saver.py — DBSaver (сохранение анкеты и документов).
"""
import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import db_saver  # noqa: E402
import services.db_saver as db_saver_module  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создать временную БД и подменить пути в модуле db_saver (через db)."""
    import services.db as db_module  # noqa: E402

    db_file = tmp_path / "test_users.db"
    users_dir = tmp_path / "Users"
    users_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(db_module, "DB_PATH", str(db_file))
    monkeypatch.setattr(db_module, "USERS_DIR", str(users_dir))

    # Инициализируем схему
    asyncio.run(db_module.init_db())

    yield str(db_file)


@pytest.mark.asyncio
async def test_save_worker_data_new(temp_db):
    """Новый работник: создаётся ID, сохраняются личные данные и документы."""
    worker_id, name = await db_saver_module.DBSaver.save_worker_data(
        user_id=12345,
        data={
            "name": "Иванов Иван",
            "citizenship": "Патент",
            "gender": "Мужской",
            "position": "Рабочий",
            "object": "Объект 1",
            "phone_main": "+79991234567",
            "saved_files": {"passport": "pas.jpg", "photo": "photo.jpg"},
        },
    )
    assert worker_id == "00001"
    assert name == "Иванов Иван"

    worker = await db_saver_module.db.get_worker(worker_id)
    assert worker is not None
    assert worker["name"] == "Иванов Иван"
    assert worker["status"] == "pending"
    assert worker["telegram_id"] == 12345

    docs = await db_saver_module.db.get_worker_documents(worker_id)
    assert "passport" in docs
    assert "photo" in docs


@pytest.mark.asyncio
async def test_save_worker_data_editing_rejected(temp_db):
    """editing_rejected=True → статус pending после сохранения."""
    # Сначала создаём работника и отклоняем его
    await db_saver_module.db.save_worker(
        {"id": "00001", "name": "Иван", "citizenship": "Патент", "status": "rejected"}
    )

    worker_id, _ = await db_saver_module.DBSaver.save_worker_data(
        user_id=12345,
        data={
            "id": "00001",
            "name": "Иван Обновлён",
            "citizenship": "Патент",
            "editing_rejected": True,
            "saved_files": {},
        },
    )
    assert worker_id == "00001"

    worker = await db_saver_module.db.get_worker(worker_id)
    assert worker["status"] == "pending"


@pytest.mark.asyncio
async def test_save_worker_data_with_telegram_username(temp_db):
    """telegram_username сохраняется если передан."""
    worker_id, _ = await db_saver_module.DBSaver.save_worker_data(
        user_id=12345,
        data={
            "name": "Иван",
            "citizenship": "Патент",
            "saved_files": {},
        },
        telegram_username="ivan_user",
    )
    worker = await db_saver_module.db.get_worker(worker_id)
    assert worker["telegram_username"] == "ivan_user"


@pytest.mark.asyncio
async def test_save_worker_data_get_next_id(temp_db, monkeypatch):
    """get_next_id делегирует в db.get_next_id."""
    called = []

    async def fake_get_next_id():
        called.append(True)
        return "99999"

    monkeypatch.setattr(db_saver_module.db, "get_next_id", fake_get_next_id)

    worker_id, _ = await db_saver_module.DBSaver.save_worker_data(
        user_id=12345,
        data={"name": "Иван", "citizenship": "Патент", "saved_files": {}},
    )
    assert worker_id == "99999"
    assert len(called) == 1
