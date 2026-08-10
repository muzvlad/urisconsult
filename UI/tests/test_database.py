"""
Тесты для слоя базы данных (database.py).
"""
import pytest
import tempfile
import json
from pathlib import Path
import sqlite3

from src.database import (
    DatabaseConnection,
    WorkerRepository,
    DocumentRepository,
    MeetingRepository,
    DatabaseService,
    init_db,
)
from src.models import Worker, WorkerDocument, WorkerMeeting


@pytest.fixture
def temp_db_path():
    """Временный путь к БД для тестов."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def db_connection(temp_db_path):
    """Соединение с тестовой БД."""
    conn = DatabaseConnection(temp_db_path)
    yield conn


@pytest.fixture
def worker_repo(db_connection):
    """Репозиторий сотрудников."""
    return WorkerRepository(db_connection)


@pytest.fixture
def doc_repo(db_connection):
    """Репозиторий документов."""
    return DocumentRepository(db_connection)


@pytest.fixture
def meeting_repo(db_connection):
    """Репозиторий встреч."""
    return MeetingRepository(db_connection)


@pytest.fixture
def sample_worker():
    """Тестовый сотрудник."""
    return Worker(
        id="TEST001",
        name="Иванов Иван Иванович",
        citizenship="Патент",
        gender="М",
        position="Водитель",
        object="Объект 1",
        object_address="ул. Ленина, 1",
        manager="Петров П.П.",
        phone_main="+79001234567",
        phone_additional="+79001112233",
        email="ivanov@example.com",
        date="01.01.1990",
        registration="Москва",
        marital_status="Женат",
        relatives_json=json.dumps([{"name": "Иванова Мария", "relation": "жена"}]),
        telegram_id=123456789,
        telegram_username="ivanov_ivan",
        created_at="2024-01-15T10:00:00",
        status="pending",
        rejection_reasons="[]",
    )


@pytest.fixture
def sample_worker_accepted():
    """Принятый сотрудник."""
    return Worker(
        id="TEST002",
        name="Петров Петр Петрович",
        citizenship="ЕАЭС",
        status="accepted",
    )


@pytest.fixture
def sample_worker_rejected():
    """Отклоненный сотрудник."""
    return Worker(
        id="TEST003",
        name="Сидоров Сидор Сидорович",
        citizenship="РВП",
        status="rejected",
        rejection_reasons=json.dumps(["passport", "photo"]),
    )


class TestDatabaseConnection:
    """Тесты DatabaseConnection."""

    def test_init_creates_tables(self, temp_db_path):
        """Инициализация создает таблицы."""
        DatabaseConnection(temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "workers" in tables
        assert "worker_documents" in tables
        assert "worker_meetings" in tables

    def test_migrations_add_columns(self, temp_db_path):
        """Миграции добавляют недостающие колонки."""
        # Создаем БД со старой схемой (без status)
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        # Инициализация должна добавить колонки
        DatabaseConnection(temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(workers)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "status" in columns
        assert "rejection_reasons" in columns

    def test_context_manager(self, db_connection):
        """Контекстный менеджер работает корректно."""
        with db_connection.get_connection() as conn:
            conn.execute("INSERT INTO workers (id, name) VALUES (?, ?)", ("TEST", "Test"))
        # Должен закоммититься автоматически

        with db_connection.get_connection() as conn:
            row = conn.execute("SELECT * FROM workers WHERE id=?", ("TEST",)).fetchone()
            assert row is not None

    def test_rollback_on_exception(self, db_connection):
        """Откат при исключении."""
        try:
            with db_connection.get_connection() as conn:
                conn.execute("INSERT INTO workers (id, name) VALUES (?, ?)", ("TEST1", "Test"))
                raise ValueError("Test error")
        except ValueError:
            pass

        with db_connection.get_connection() as conn:
            row = conn.execute("SELECT * FROM workers WHERE id=?", ("TEST1",)).fetchone()
            assert row is None  # Должен откатиться


class TestWorkerRepository:
    """Тесты WorkerRepository."""

    def test_create_and_get_by_id(self, worker_repo, sample_worker):
        """Создание и получение по ID."""
        assert worker_repo.create(sample_worker) is True

        worker = worker_repo.get_by_id("TEST001")
        assert worker is not None
        assert worker.id == "TEST001"
        assert worker.name == "Иванов Иван Иванович"
        assert worker.status == "pending"

    def test_create_duplicate_fails(self, worker_repo, sample_worker):
        """Дубликат ID не создается."""
        worker_repo.create(sample_worker)
        assert worker_repo.create(sample_worker) is False

    def test_get_all(self, worker_repo, sample_worker, sample_worker_accepted):
        """Получение всех."""
        worker_repo.create(sample_worker)
        worker_repo.create(sample_worker_accepted)

        workers = worker_repo.get_all()
        assert len(workers) == 2

    def test_search_by_name(self, worker_repo, sample_worker):
        """Поиск по имени."""
        worker_repo.create(sample_worker)

        results = worker_repo.search("Иванов")
        assert len(results) == 1
        assert results[0].id == "TEST001"

    def test_search_partial_match(self, worker_repo, sample_worker):
        """Частичное совпадение."""
        worker_repo.create(sample_worker)

        results = worker_repo.search("Иван")
        assert len(results) == 1

    def test_search_multiple_fields(self, worker_repo, sample_worker):
        """Поиск по разным полям."""
        worker_repo.create(sample_worker)

        # По телефону
        results = worker_repo.search("9001234567")
        assert len(results) == 1

        # По email
        results = worker_repo.search("ivanov@example.com")
        assert len(results) == 1

    def test_get_by_status(self, worker_repo, sample_worker, sample_worker_accepted, sample_worker_rejected):
        """Получение по статусу."""
        worker_repo.create(sample_worker)
        worker_repo.create(sample_worker_accepted)
        worker_repo.create(sample_worker_rejected)

        pending = worker_repo.get_pending()
        accepted = worker_repo.get_accepted()
        rejected = worker_repo.get_rejected()

        assert len(pending) == 1
        assert pending[0].id == "TEST001"

        assert len(accepted) == 1
        assert accepted[0].id == "TEST002"

        assert len(rejected) == 1
        assert rejected[0].id == "TEST003"

    def test_count_by_status(self, worker_repo, sample_worker, sample_worker_accepted):
        """Подсчет по статусу."""
        worker_repo.create(sample_worker)
        worker_repo.create(sample_worker_accepted)

        assert worker_repo.count_by_status("pending") == 1
        assert worker_repo.count_by_status("accepted") == 1
        assert worker_repo.count_by_status("rejected") == 0

    def test_update_status_accept(self, worker_repo, sample_worker):
        """Обновление статуса - принять."""
        worker_repo.create(sample_worker)
        assert worker_repo.accept("TEST001") is True

        worker = worker_repo.get_by_id("TEST001")
        assert worker.status == "accepted"
        assert worker.rejection_reasons == "[]"

    def test_update_status_reject(self, worker_repo, sample_worker):
        """Обновление статуса - отклонить."""
        worker_repo.create(sample_worker)
        assert worker_repo.reject("TEST001", ["passport", "photo"]) is True

        worker = worker_repo.get_by_id("TEST001")
        assert worker.status == "rejected"
        reasons = json.loads(worker.rejection_reasons)
        assert reasons == ["passport", "photo"]

    def test_update_status_nonexistent(self, worker_repo):
        """Обновление несуществующего."""
        assert worker_repo.accept("NONEXISTENT") is False

    def test_update_worker(self, worker_repo, sample_worker):
        """Обновление полей работника."""
        worker_repo.create(sample_worker)

        sample_worker.name = "Иванов Иван Иванович (изменено)"
        sample_worker.position = "Старший водитель"
        assert worker_repo.update(sample_worker) is True

        worker = worker_repo.get_by_id("TEST001")
        assert worker.name == "Иванов Иван Иванович (изменено)"
        assert worker.position == "Старший водитель"


class TestDocumentRepository:
    """Тесты DocumentRepository."""

    def test_add_and_get(self, doc_repo):
        """Добавление и получение документа."""
        assert doc_repo.add("TEST001", "passport", "pas_TEST001.jpg") is True

        filename = doc_repo.get_document("TEST001", "passport")
        assert filename == "pas_TEST001.jpg"

    def test_get_by_worker(self, doc_repo):
        """Получение всех документов работника."""
        doc_repo.add("TEST001", "passport", "pas_TEST001.jpg")
        doc_repo.add("TEST001", "photo", "photo_TEST001.jpg")

        docs = doc_repo.get_by_worker("TEST001")
        assert docs == {
            "passport": ["pas_TEST001.jpg"],
            "photo": ["photo_TEST001.jpg"],
        }

    def test_update_document(self, doc_repo):
        """Обновление документа (INSERT OR REPLACE)."""
        doc_repo.add("TEST001", "passport", "old.jpg")
        doc_repo.add("TEST001", "passport", "new.jpg")

        filename = doc_repo.get_document("TEST001", "passport")
        assert filename == "new.jpg"

    def test_delete_document(self, doc_repo):
        """Удаление документа."""
        doc_repo.add("TEST001", "passport", "pas_TEST001.jpg")
        assert doc_repo.delete("TEST001", "passport") is True
        assert doc_repo.get_document("TEST001", "passport") is None

    def test_delete_nonexistent(self, doc_repo):
        """Удаление несуществующего."""
        assert doc_repo.delete("TEST001", "passport") is False

    def test_clear_worker(self, doc_repo):
        """Очистка всех документов работника."""
        doc_repo.add("TEST001", "passport", "pas_TEST001.jpg")
        doc_repo.add("TEST001", "photo", "photo_TEST001.jpg")
        assert doc_repo.clear_worker("TEST001") is True
        assert doc_repo.get_by_worker("TEST001") == {}


class TestMeetingRepository:
    """Тесты MeetingRepository."""

    def test_add_and_get(self, meeting_repo):
        """Добавление и получение встреч."""
        meeting_repo.add("TEST001", "2024-01-15", "Первая встреча")
        meeting_repo.add("TEST001", "2024-01-20", "Вторая встреча")

        meetings = meeting_repo.get_by_worker("TEST001")
        assert len(meetings) == 2
        assert meetings[0]["date"] == "2024-01-15"
        assert meetings[0]["note"] == "Первая встреча"
        assert meetings[1]["date"] == "2024-01-20"

    def test_get_empty(self, meeting_repo):
        """Получение для работника без встреч."""
        meetings = meeting_repo.get_by_worker("NONEXISTENT")
        assert meetings == []


class TestDatabaseService:
    """Тесты фасада DatabaseService."""

    def test_init_creates_all_repos(self, temp_db_path):
        """Инициализация создает все репозитории."""
        service = DatabaseService(temp_db_path)
        assert service.workers is not None
        assert service.documents is not None
        assert service.meetings is not None

    def test_full_workflow(self, temp_db_path, sample_worker):
        """Полный рабочий процесс."""
        service = DatabaseService(temp_db_path)

        # Создание
        assert service.workers.create(sample_worker) is True

        # Добавление документов
        assert service.documents.add("TEST001", "passport", "pas_TEST001.jpg") is True
        assert service.documents.add("TEST001", "photo", "photo_TEST001.jpg") is True

        # Добавление встречи
        assert service.meetings.add("TEST001", "2024-01-15", "Собеседование") is True

        # Проверка
        worker = service.workers.get_by_id("TEST001")
        assert worker is not None

        docs = service.documents.get_by_worker("TEST001")
        assert len(docs) == 2

        meetings = service.meetings.get_by_worker("TEST001")
        assert len(meetings) == 1


class TestInitDB:
    """Тесты функции init_db."""

    def test_init_db_creates_schema(self, temp_db_path):
        """init_db создает схему."""
        init_db(temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "workers" in tables
        assert "worker_documents" in tables
        assert "worker_meetings" in tables

    def test_init_db_idempotent(self, temp_db_path):
        """Многократный вызов не вызывает ошибок."""
        init_db(temp_db_path)
        init_db(temp_db_path)  # Не должно упасть
        init_db(temp_db_path)


class TestWorkerModel:
    """Тесты модели Worker."""

    def test_from_row(self):
        """Создание из sqlite3.Row."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                name TEXT,
                citizenship TEXT,
                status TEXT DEFAULT 'pending',
                rejection_reasons TEXT DEFAULT '[]'
            )
        """)
        cursor.execute(
            "INSERT INTO workers (id, name, citizenship, status, rejection_reasons) VALUES (?, ?, ?, ?, ?)",
            ("TEST", "Test Worker", "Патент", "rejected", '["passport"]')
        )
        conn.commit()

        row = cursor.execute("SELECT * FROM workers WHERE id=?", ("TEST",)).fetchone()
        worker = Worker.from_row(row)

        assert worker.id == "TEST"
        assert worker.name == "Test Worker"
        assert worker.status == "rejected"
        assert worker.reasons == ["passport"]

    def test_to_dict(self, sample_worker):
        """Сериализация в словарь."""
        data = sample_worker.to_dict()
        assert data["id"] == "TEST001"
        assert data["name"] == "Иванов Иван Иванович"
        assert data["status"] == "pending"

    def test_properties(self, sample_worker, sample_worker_accepted, sample_worker_rejected):
        """Свойства статуса."""
        assert sample_worker.is_pending is True
        assert sample_worker.is_accepted is False
        assert sample_worker.is_rejected is False

        assert sample_worker_accepted.is_accepted is True

        assert sample_worker_rejected.is_rejected is True
        assert sample_worker_rejected.reasons == ["passport", "photo"]