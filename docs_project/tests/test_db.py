"""
Тесты для bot/services/db.py — нормализованная БД.

Запуск: cd docs_project && python -m pytest tests/test_db.py -v
"""
import os
import sys
import asyncio
import sqlite3
import json
import tempfile
import shutil
import pytest

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)


@pytest.fixture(autouse=True)
def reset_db_singleton():
    """Сброс синглтона БД перед каждым тестом."""
    import services.db as db_module
    db_module._db = None
    # pytest-asyncio (bot/tests) очищает event loop потока после себя —
    # гарантируем свежий loop на время теста
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield
    # Cleanup после теста
    loop.close()
    asyncio.set_event_loop(None)
    db_module._db = None


@pytest.fixture
def fresh_db(tmp_path):
    """Создаёт свежую БД в tmp_path и возвращает путь к ней."""
    db_path = str(tmp_path / "test_users.db")
    users_dir = str(tmp_path / "Users")
    docs_dir = str(tmp_path / "users" / "docs")
    os.makedirs(users_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    return db_path, users_dir, docs_dir


@pytest.fixture
def sample_personal_data():
    return {
        'id': '00001',
        'name': 'Иванов Иван Иванович',
        'citizenship': 'Патент',
        'gender': 'Мужской',
        'position': 'Электрик',
        'object': 'Жилой дом',
        'object_address': 'ул. Пушкина, д. 10',
        'manager': 'Петров П.П.',
        'phone_main': '+79991234567',
        'phone_additional': 'Не указан',
        'email': 'ivanov@test.com',
        'date': '01.01.1990',
    }


@pytest.fixture
def sample_doc_files():
    return {
        'photo': 'photo_00001.jpg',
        'passport': 'pas_00001.jpg',
        'patent_snils': 'snils_00001.jpg',
    }


def _patch_db_module(db_path, users_dir, docs_dir):
    """Патчит модуль db на временные пути."""
    import services.db as db_module
    db_module.DB_PATH = db_path
    db_module.USERS_DIR = users_dir
    db_module.DOCS_DIR = docs_dir
    return db_module


class TestDatabaseSchema:
    def test_init_db_creates_tables(self, fresh_db):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert 'workers' in tables
        assert 'worker_documents' in tables
        assert 'worker_meetings' in tables

    def test_v5_database_migrates_to_v6(self, fresh_db):
        db_path, users_dir, docs_dir = fresh_db
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE workers (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "status TEXT DEFAULT 'pending', created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE worker_meetings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "worker_id TEXT NOT NULL, date TEXT, note TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute("INSERT INTO workers (id, name) VALUES ('00001', 'Иванов')")
        conn.execute(
            "INSERT INTO worker_meetings (worker_id, date) VALUES ('00001', '01.01.2027 10:00')"
        )
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
        conn.close()

        db_module = _patch_db_module(db_path, users_dir, docs_dir)
        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        conn = sqlite3.connect(db_path)
        worker_cols = {r[1] for r in conn.execute("PRAGMA table_info(workers)")}
        meeting_cols = {r[1] for r in conn.execute("PRAGMA table_info(worker_meetings)")}
        meeting = conn.execute(
            "SELECT notified_at, reminded_at FROM worker_meetings").fetchone()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()

        assert {'customer', 'legal_entity', 'hr_status', 'archived_at', 'documents_signed'} <= worker_cols
        assert {'notified_at', 'reminded_at'} <= meeting_cols
        assert meeting[0] and meeting[1]
        assert version == 7

    def test_workers_table_columns(self, fresh_db):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(workers)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {
            'id', 'name', 'citizenship', 'gender', 'position',
            'object', 'object_address', 'manager',
            'phone_main', 'phone_additional', 'email', 'date',
            'registration', 'marital_status', 'relatives_json',
            'telegram_id', 'telegram_username', 'created_at',
        }
        assert expected.issubset(columns)


class TestWorkerCRUD:
    def test_save_and_get_worker(self, fresh_db, sample_personal_data, sample_doc_files):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.save_documents('00001', sample_doc_files)
        )
        worker = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker('00001')
        )

        assert worker is not None
        assert worker['name'] == 'Иванов Иван Иванович'
        assert worker['citizenship'] == 'Патент'

        docs = worker['documents']
        assert docs['photo'][0]['filename'] == 'photo_00001.jpg'
        assert docs['passport'][0]['filename'] == 'pas_00001.jpg'
        assert docs['patent_snils'][0]['filename'] == 'snils_00001.jpg'

    def test_get_nonexistent_worker(self, fresh_db):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        worker = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker('99999')
        )
        assert worker is None

    def test_get_all_workers(self, fresh_db, sample_personal_data):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )

        data2 = sample_personal_data.copy()
        data2['id'] = '00002'
        data2['name'] = 'Петров Пётр Петрович'
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(data2)
        )

        all_workers = asyncio.get_event_loop().run_until_complete(
            db_module.get_all_workers()
        )
        assert len(all_workers) == 2

    def test_get_next_id_empty(self, fresh_db):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        next_id = asyncio.get_event_loop().run_until_complete(
            db_module.get_next_id()
        )
        assert next_id == '00001'

    def test_get_next_id_incremental(self, fresh_db, sample_personal_data):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        next_id = asyncio.get_event_loop().run_until_complete(
            db_module.get_next_id()
        )
        assert next_id == '00002'

    def test_search_workers(self, fresh_db, sample_personal_data):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )

        results = asyncio.get_event_loop().run_until_complete(
            db_module.search_workers('Иванов')
        )
        assert len(results) == 1
        assert results[0]['name'] == 'Иванов Иван Иванович'

        results_empty = asyncio.get_event_loop().run_until_complete(
            db_module.search_workers('Несуществующий')
        )
        assert len(results_empty) == 0

    def test_reserved_not_in_list(self, fresh_db, sample_personal_data):
        """__reserved__ заглушки не попадают в список всех и поиск."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        # get_next_id создаёт строку-заглушку __reserved__
        reserved_id = asyncio.get_event_loop().run_until_complete(
            db_module.get_next_id()
        )
        assert reserved_id == '00002'

        all_workers = asyncio.get_event_loop().run_until_complete(
            db_module.get_all_workers()
        )
        assert any(w['id'] == '00001' for w in all_workers)
        assert not any(w['name'] == '__reserved__' for w in all_workers)

        search_results = asyncio.get_event_loop().run_until_complete(
            db_module.search_workers('Иванов')
        )
        assert all(w['name'] != '__reserved__' for w in search_results)

    def test_save_worker_with_existing_id_no_extra_reserved(self, fresh_db, sample_personal_data):
        """Сохранение с уже заданным id НЕ должно плодить новые __reserved__ строки."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        import services.db as real_db_module
        from services.db_saver import DBSaver

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        # DBSaver использует тот же services.db (пропатченный на временные пути)
        for _ in range(3):
            asyncio.get_event_loop().run_until_complete(
                DBSaver.save_worker_data(
                    user_id=999, data=sample_personal_data.copy()
                )
            )

        all_workers = asyncio.get_event_loop().run_until_complete(
            db_module.get_all_workers()
        )
        # id уже есть в данных — get_next_id не должен вызываться, резервов нет
        assert len(all_workers) == 1
        assert all(w['name'] != '__reserved__' for w in all_workers)

    def test_resubmit_rejected_returns_pending(self, fresh_db, sample_personal_data):
        """Исправление отклонённой анкеты возвращает её в статус pending."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        from services.db_saver import DBSaver

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        data = sample_personal_data.copy()
        data['id'] = '00042'

        asyncio.get_event_loop().run_until_complete(
            DBSaver.save_worker_data(user_id=999, data=data.copy())
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.reject_worker('00042', ['patent_inn'])
        )
        worker = asyncio.get_event_loop().run_until_complete(db_module.get_worker('00042'))
        assert worker['status'] == 'rejected'

        # Клиент исправляет анкету и подтверждает
        data['editing_rejected'] = True
        asyncio.get_event_loop().run_until_complete(
            DBSaver.save_worker_data(user_id=999, data=data.copy())
        )

        worker = asyncio.get_event_loop().run_until_complete(db_module.get_worker('00042'))
        assert worker['status'] == 'pending'
        assert worker['rejection_reasons'] == '[]'

        pending = asyncio.get_event_loop().run_until_complete(db_module.get_pending_workers())
        assert any(w['id'] == '00042' for w in pending)

    def test_reject_worker_with_comments(self, fresh_db, sample_personal_data):
        """Отклонение с комментариями сохраняет {key, comment} в rejection_reasons."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.reject_worker('00001', [{'key': 'patent_inn', 'comment': 'Номер не читается'}])
        )

        worker = asyncio.get_event_loop().run_until_complete(db_module.get_worker('00001'))
        import json as _json
        reasons = _json.loads(worker['rejection_reasons'])
        assert reasons == [{'key': 'patent_inn', 'comment': 'Номер не читается'}]

    def test_save_documents_replaces_old(self, fresh_db, sample_personal_data):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.save_documents('00001', {'photo': 'photo_v1.jpg'})
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.save_documents('00001', {'photo': 'photo_v2.jpg'})
        )

        docs = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker_documents('00001')
        )
        assert [d['filename'] for d in docs['photo']] == ['photo_v2.jpg']

    def test_save_documents_multi_file(self, fresh_db, sample_personal_data):
        """Несколько файлов одного документа сохраняются и читаются."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.save_documents('00001', {'vnzh_work_book': ['trud.jpg', 'trud_2.jpg']})
        )

        docs = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker_documents('00001')
        )
        assert [d['filename'] for d in docs['vnzh_work_book']] == ['trud.jpg', 'trud_2.jpg']

    def test_replace_document(self, fresh_db, sample_personal_data):
        """Перезаливка: запись остаётся, имя файла прежнее, created_at обновляется."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(sample_personal_data)
        )
        asyncio.get_event_loop().run_until_complete(
            db_module.save_documents('00001', {'photo': 'photo_v1.jpg'})
        )
        docs_before = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker_documents('00001')
        )
        old_created = docs_before['photo'][0]['created_at']

        asyncio.get_event_loop().run_until_complete(
            db_module.replace_document('00001', 'photo', 'photo_v1.jpg')
        )

        docs = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker_documents('00001')
        )
        assert [d['filename'] for d in docs['photo']] == ['photo_v1.jpg']
        assert docs['photo'][0]['created_at'] != old_created

    def test_save_worker_fills_dates(self, fresh_db, sample_personal_data):
        """save_worker гарантирует created_at/updated_at."""
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        data = sample_personal_data.copy()
        data.pop('created_at', None)
        data.pop('updated_at', None)
        asyncio.get_event_loop().run_until_complete(db_module.save_worker(data))

        worker = asyncio.get_event_loop().run_until_complete(db_module.get_worker('00001'))
        assert worker['created_at']
        assert worker['updated_at']


class TestWorkerMeetings:
    def test_save_worker_with_meetings(self, fresh_db, sample_personal_data):
        db_path, users_dir, docs_dir = fresh_db
        db_module = _patch_db_module(db_path, users_dir, docs_dir)

        asyncio.get_event_loop().run_until_complete(db_module.init_db())

        data = sample_personal_data.copy()
        data['meetings'] = [
            {'date': '01.07.2026', 'note': 'Первая встреча'},
            {'date': '05.07.2026', 'note': 'Вторая встреча'},
        ]
        asyncio.get_event_loop().run_until_complete(
            db_module.save_worker(data)
        )

        worker = asyncio.get_event_loop().run_until_complete(
            db_module.get_worker('00001')
        )
        assert len(worker['meetings_list']) == 2


# TestDatabaseSingleton удалён — бот больше не использует синглтон-соединение.
# Каждая операция открывает своё соединение и сразу закрывает.
