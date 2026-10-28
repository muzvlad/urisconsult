"""
Тесты для bot/services/db.py — слой работы с SQLite.

Использует временный файл БД в tmp_path, подменяет db.DB_PATH и db.USERS_DIR.
"""
import asyncio
import json
import os
import sys
import tempfile

import pytest

# Добавляем bot/ в pythonpath для импортов (как в pytest.ini)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import db  # noqa: E402
import services.db as db_module  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создать временную БД и подменить пути в модуле db."""
    db_file = tmp_path / "test_users.db"
    users_dir = tmp_path / "Users"
    users_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(db_module, "DB_PATH", str(db_file))
    monkeypatch.setattr(db_module, "USERS_DIR", str(users_dir))

    # Инициализируем схему
    asyncio.run(db_module.init_db())

    yield str(db_file)


# ─── get_next_id ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_next_id_first(temp_db):
    """Первый ID — 00001."""
    nid = await db.get_next_id()
    assert nid == "00001"


@pytest.mark.asyncio
async def test_get_next_id_increments(temp_db):
    """ID увеличиваются при повторном вызове."""
    nid1 = await db.get_next_id()
    nid2 = await db.get_next_id()
    assert int(nid2) == int(nid1) + 1


@pytest.mark.asyncio
async def test_get_next_id_unique(temp_db):
    """get_next_id не возвращает существующие ID."""
    await db.get_next_id()
    await db.get_next_id()
    nid3 = await db.get_next_id()
    assert nid3 == "00003"


# ─── save_worker / get_worker ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_get_worker(temp_db):
    """Сохранение и чтение работника."""
    worker_id = await db.save_worker({
        "id": "00001",
        "name": "Иванов Иван",
        "citizenship": "Патент",
        "gender": "Мужской",
        "position": "Рабочий",
        "object": "Объект 1",
        "phone_main": "+79991234567",
        "telegram_id": 12345,
    })
    assert worker_id == "00001"

    worker = await db.get_worker("00001")
    assert worker is not None
    assert worker["name"] == "Иванов Иван"
    assert worker["citizenship"] == "Патент"
    assert worker["status"] == "pending"
    assert worker["telegram_id"] == 12345


@pytest.mark.asyncio
async def test_get_worker_not_found(temp_db):
    """get_worker возвращает None для несуществующего ID."""
    result = await db.get_worker("99999")
    assert result is None


@pytest.mark.asyncio
async def test_save_worker_update(temp_db):
    """UPDATE существующего работника (ON CONFLICT)."""
    await db.save_worker({"id": "00001", "name": "Иванов Иван", "citizenship": "Патент"})
    await db.save_worker({"id": "00001", "name": "Петров Пётр", "citizenship": "Россия"})

    worker = await db.get_worker("00001")
    assert worker["name"] == "Петров Пётр"
    assert worker["citizenship"] == "Россия"


@pytest.mark.asyncio
async def test_save_worker_created_at_not_overwritten(temp_db):
    """created_at не перезаписывается при UPDATE."""
    await db.save_worker({"id": "00001", "name": "Иван", "created_at": "2024-01-01T00:00:00"})
    worker = await db.get_worker("00001")
    assert worker["created_at"] == "2024-01-01T00:00:00"

    await db.save_worker({"id": "00001", "name": "Иван Обновлён"})
    worker = await db.get_worker("00001")
    assert worker["created_at"] == "2024-01-01T00:00:00"
    assert worker["name"] == "Иван Обновлён"


# ─── save_documents / get_worker_documents ────────────────────────────

@pytest.mark.asyncio
async def test_save_and_get_documents(temp_db):
    """Сохранение и чтение документов."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    await db.save_documents("00001", {"passport": "pas.jpg", "photo": "photo.jpg"})

    docs = await db.get_worker_documents("00001")
    assert "passport" in docs
    assert "photo" in docs
    assert docs["passport"][0]["filename"] == "pas.jpg"


@pytest.mark.asyncio
async def test_save_documents_multi_file(temp_db):
    """Мультифайловый документ — список имён."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Россия"})
    await db.save_documents("00001", {"russia_work_book": ["trud_1.jpg", "trud_2.jpg"]})

    docs = await db.get_worker_documents("00001")
    assert len(docs["russia_work_book"]) == 2
    assert docs["russia_work_book"][0]["filename"] == "trud_1.jpg"
    assert docs["russia_work_book"][1]["filename"] == "trud_2.jpg"


@pytest.mark.asyncio
async def test_replace_document(temp_db):
    """replace_document: запись остаётся, имя прежнее, created_at обновляется."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    await db.save_documents("00001", {"passport": "pas_old.jpg"})
    before = (await db.get_worker_documents("00001"))["passport"][0]["created_at"]

    await db.replace_document("00001", "passport", "pas_old.jpg")

    docs = await db.get_worker_documents("00001")
    assert [d["filename"] for d in docs["passport"]] == ["pas_old.jpg"]
    assert docs["passport"][0]["created_at"] != before


# ─── get_all_workers / search_workers ─────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_workers(temp_db):
    """get_all_workers возвращает всех без сирот."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    await db.save_worker({"id": "00002", "name": "Пётр", "citizenship": "Россия"})
    await db.save_worker({"id": "__reserved__", "name": "__reserved__", "citizenship": ""})

    workers = await db.get_all_workers()
    ids = [w["id"] for w in workers]
    assert "00001" in ids
    assert "00002" in ids
    assert "__reserved__" not in ids


@pytest.mark.asyncio
async def test_search_workers(temp_db):
    """search_workers ищет по части имени."""
    await db.save_worker({"id": "00001", "name": "Иванов Иван", "citizenship": "Патент"})
    await db.save_worker({"id": "00002", "name": "Петров Пётр", "citizenship": "Россия"})

    results = await db.search_workers("Иван")
    assert len(results) == 1
    assert results[0]["name"] == "Иванов Иван"

    results = await db.search_workers("Пётр")
    assert len(results) == 1
    assert results[0]["name"] == "Петров Пётр"


# ─── Статусы ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accept_reject_resubmit_worker(temp_db):
    """Переключение статусов pending ↔ accepted ↔ rejected."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент", "status": "pending"})

    await db.accept_worker("00001")
    assert await db.get_worker_status("00001") == "accepted"

    await db.reject_worker("00001", ["passport"])
    assert await db.get_worker_status("00001") == "rejected"

    await db.resubmit_worker("00001")
    assert await db.get_worker_status("00001") == "pending"


@pytest.mark.asyncio
async def test_get_pending_count(temp_db):
    """get_pending_count считает только pending без сирот и архива."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    await db.save_worker({"id": "00002", "name": "Пётр", "citizenship": "Россия"})
    await db.accept_worker("00002")  # Пётр становится accepted
    await db.save_worker({"id": "__reserved__", "name": "__reserved__", "citizenship": "", "status": "pending"})

    count = await db.get_pending_count()
    assert count == 1


# ─── UI-поля ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_legal_entity(temp_db):
    """set_legal_entity сохраняет юр. лицо."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    result = await db.set_legal_entity("00001", "ООО Ромашка")
    assert result is True

    worker = await db.get_worker("00001")
    assert worker["legal_entity"] == "ООО Ромашка"


@pytest.mark.asyncio
async def test_set_hr_status(temp_db):
    """set_hr_status сохраняет HR-статус с датой."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    result = await db.set_hr_status("00001", "employed", "2024-01-15")
    assert result is True

    worker = await db.get_worker("00001")
    assert worker["hr_status"] == "employed"
    assert worker["hr_status_date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_set_hr_status_requires_date(temp_db):
    """employed/fired требуют дату."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    result = await db.set_hr_status("00001", "employed", None)
    assert result is False

    result = await db.set_hr_status("00001", "not_processed", None)
    assert result is True


# ─── Архив ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_unarchive_worker(temp_db):
    """archive_worker / unarchive_worker."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})

    result = await db.archive_worker("00001")
    assert result is True
    worker = await db.get_worker("00001")
    assert worker["archived_at"] is not None and worker["archived_at"] != ""

    result = await db.unarchive_worker("00001")
    assert result is True
    worker = await db.get_worker("00001")
    assert worker["archived_at"] is None or worker["archived_at"] == ""


# ─── delete_worker ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_worker_cascades(temp_db):
    """delete_worker удаляет работника и все связанные записи."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    await db.save_documents("00001", {"passport": "pas.jpg"})
    await db.add_meeting("00001", "2024-02-01", "Встреча")
    await db.add_worker_note("00001", "Заметка")

    result = await db.delete_worker("00001")
    assert result is True

    assert await db.get_worker("00001") is None
    assert await db.get_worker_documents("00001") == {}
    meetings = await db.get_unnotified_meetings()
    assert all(m["worker_id"] != "00001" for m in meetings)
    notes = await db.get_worker_notes("00001")
    assert notes == []


# ─── Встречи ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_get_meetings(temp_db):
    """CRUD встреч."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент", "telegram_id": 123})
    mid = await db.add_meeting("00001", "2024-02-01 10:00", "Первая встреча")
    assert mid == 1

    meetings = await db.get_unnotified_meetings()
    assert len(meetings) == 1
    assert meetings[0]["date"] == "2024-02-01 10:00"
    assert meetings[0]["note"] == "Первая встреча"
    assert meetings[0]["worker_name"] == "Иван"


@pytest.mark.asyncio
async def test_mark_meeting_notified_reminded(temp_db):
    """Пометка встречи как уведомлённой и напомненной."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент", "telegram_id": 123})
    mid = await db.add_meeting("00001", "2024-02-01", "Встреча")

    await db.mark_meeting_notified(mid, "2024-01-31T10:00:00")
    meetings = await db.get_unnotified_meetings()
    assert len(meetings) == 0

    await db.mark_meeting_reminded(mid, "2024-01-31T11:00:00")
    remind = await db.get_meetings_to_remind()
    assert len(remind) == 0


# ─── Комментарии ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_update_delete_note(temp_db):
    """CRUD комментариев."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})

    note_id = await db.add_worker_note("00001", "Первая заметка")
    assert note_id == 1

    notes = await db.get_worker_notes("00001")
    assert len(notes) == 1
    assert notes[0]["text"] == "Первая заметка"

    result = await db.update_worker_note(note_id, "Обновлённая заметка")
    assert result is True
    notes = await db.get_worker_notes("00001")
    assert notes[0]["text"] == "Обновлённая заметка"

    result = await db.delete_worker_note(note_id)
    assert result is True
    notes = await db.get_worker_notes("00001")
    assert notes == []


@pytest.mark.asyncio
async def test_add_note_empty_text(temp_db):
    """Пустой текст комментария не сохраняется."""
    await db.save_worker({"id": "00001", "name": "Иван", "citizenship": "Патент"})
    result = await db.add_worker_note("00001", "")
    assert result is None

    result = await db.add_worker_note("00001", "   ")
    assert result is None


# ─── Миграция ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_init_db_schema_version(temp_db):
    """init_db устанавливает PRAGMA user_version = 6."""
    import aiosqlite
    async with aiosqlite.connect(db_module.DB_PATH) as conn:
        cursor = await conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        assert row[0] == 6


@pytest.mark.asyncio
async def test_init_db_tables_exist(temp_db):
    """init_db создаёт все 4 таблицы."""
    import aiosqlite
    async with aiosqlite.connect(db_module.DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "workers" in tables
        assert "worker_documents" in tables
        assert "worker_meetings" in tables
        assert "worker_notes" in tables


@pytest.mark.asyncio
async def test_init_db_keeps_fresh_reserved(temp_db):
    """Свежий резерв __reserved__ переживает init_db.

    Раньше init_db удалял все резервы, и живой резерв другого процесса
    исчезал — тот же ID выдавался дважды.
    """
    import aiosqlite

    reserved_id = await db.get_next_id()

    async with aiosqlite.connect(db_module.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT name, created_at FROM workers WHERE id = ?", (reserved_id,)
        )
        row = await cursor.fetchone()
        assert row["name"] == db_module.RESERVED_NAME
        assert row["created_at"]  # отметка времени нужна для старения резерва

    await db_module.init_db()

    async with aiosqlite.connect(db_module.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT name FROM workers WHERE id = ?", (reserved_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == db_module.RESERVED_NAME
