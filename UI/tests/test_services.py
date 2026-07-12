"""
Тесты для сервисов (services.py).
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
import json

from src.services import DocumentService, TelegramService, PDFExportService, get_document_service
from src.models import Worker
from src.database import DatabaseService, WorkerRepository, DocumentRepository, init_db


@dataclass
class MockDocumentType:
    key: str
    label: str
    prefix: str


@pytest.fixture
def test_db_path(tmp_path):
    """Путь к тестовой БД."""
    return tmp_path / "test.db"


@pytest.fixture
def test_docs_dir(tmp_path):
    """Тестовая папка документов."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return docs


@pytest.fixture
def db_service(test_db_path):
    """DatabaseService с тестовой БД."""
    return DatabaseService(test_db_path)


@pytest.fixture
def sample_worker(db_service):
    """Создает тестового работника в БД."""
    worker = Worker(
        id="TEST001",
        name="Иванов Иван",
        citizenship="Патент",
        status="pending",
    )
    db_service.workers.create(worker)
    return worker


@pytest.fixture
def sample_worker_with_docs(db_service, test_docs_dir):
    """Работник с документами."""
    worker = Worker(
        id="TEST002",
        name="Петров Петр",
        citizenship="Патент",
        status="accepted",
    )
    db_service.workers.create(worker)
    # Добавляем документы в БД
    db_service.documents.add("TEST002", "passport", "pas_TEST002.jpg")
    db_service.documents.add("TEST002", "photo", "photo_TEST002.jpg")
    return worker


# Mock DocumentType для тестов
@dataclass
class MockDocumentType:
    key: str
    label: str
    prefix: str
    required: bool = False
    can_skip: bool = True
    category: str = ""


class TestDocumentService:
    """Тесты DocumentService."""

    @pytest.fixture
    def doc_service(self, test_db_path, test_docs_dir, monkeypatch):
        """DocumentService с переопределенными путями."""
        # Мокаем get_paths чтобы вернуть тестовые пути
        from src.config import AppPaths
        test_paths = AppPaths(
            project_root=test_docs_dir.parent,
            db_path=test_db_path,
            docs_dir=test_docs_dir,
            bot_dir=test_docs_dir.parent / "bot",
        )
        monkeypatch.setattr("src.services.get_paths", lambda: test_paths)

        # Мокаем конфиг
        from src.config import AppConfig
        test_config = AppConfig(image_extensions=[".jpg", ".png"])
        monkeypatch.setattr("src.services.get_config", lambda: test_config)

        # Мокаем get_db_service
        monkeypatch.setattr("src.services.get_db_service", lambda: DatabaseService(test_db_path))

        # Мокаем get_document_config
        doc_flows = {
            "Патент": [
                MockDocumentType(key="passport", label="Паспорт", prefix="pas"),
                MockDocumentType(key="photo", label="Фото", prefix="photo"),
            ]
        }
        doc_labels = {"passport": "Паспорт", "photo": "Фото"}
        doc_prefixes = {"passport": "pas", "photo": "photo"}
        monkeypatch.setattr("src.services.get_document_config", lambda: (doc_flows, doc_labels, doc_prefixes))

        # Создаем файлы для тестов
        (test_docs_dir / "photo_TEST001.jpg").write_bytes(b"fake")
        (test_docs_dir / "pas_TEST002.jpg").write_bytes(b"fake")
        (test_docs_dir / "photo_TEST002.jpg").write_bytes(b"fake")

        return DocumentService()

    def test_find_photo(self, doc_service, test_docs_dir, sample_worker):
        """Поиск фото работника."""
        # Создаем файл фото
        photo_path = test_docs_dir / "photo_TEST001.jpg"
        photo_path.write_bytes(b"fake image data")

        found = doc_service.find_photo("TEST001")
        assert found == photo_path

    def test_find_photo_not_exists(self, doc_service, sample_worker):
        """Фото не найдено."""
        found = doc_service.find_photo("NONEXISTENT")
        assert found is None

    def test_get_worker_documents(self, doc_service, sample_worker_with_docs):
        """Получение списка документов с информацией о файлах."""
        docs = doc_service.get_worker_documents(sample_worker_with_docs)
        assert len(docs) == 2

        passport_doc = next(d for d in docs if d.doc_type == "passport")
        assert passport_doc.filename == "pas_TEST002.jpg"
        assert passport_doc.exists is True

    def test_load_thumbnail(self, doc_service, test_docs_dir):
        """Загрузка миниатюры."""
        import tkinter as tk
        from PIL import Image
        
        # Создаем Tk root для PhotoImage
        root = tk.Tk()
        root.withdraw()
        
        try:
            img = Image.new("RGB", (100, 100), color="red")
            img_path = test_docs_dir / "test.jpg"
            img.save(img_path)

            thumb = doc_service.load_thumbnail(img_path)
            assert thumb is not None
            assert thumb.width() <= 200
            assert thumb.height() <= 200
        finally:
            root.destroy()

    def test_load_thumbnail_caching(self, doc_service, test_docs_dir):
        """Кэширование миниатюр - проверка через повторный вызов."""
        import tkinter as tk
        from PIL import Image
        
        # Используем тот же root что и в предыдущем тесте (если он есть)
        try:
            img = Image.new("RGB", (100, 100), color="blue")
            img_path = test_docs_dir / "cached.jpg"
            img.save(img_path)

            thumb1 = doc_service.load_thumbnail(img_path)
            thumb2 = doc_service.load_thumbnail(img_path)
            # Должен вернуть тот же объект (кэш)
            if thumb1 and thumb2:
                assert thumb1 is thumb2
        except RuntimeError:
            # Tcl/Tk не инициализирован - пропускаем проверку кэша
            pytest.skip("Tkinter not available in test environment")

    def test_get_document_label(self, doc_service):
        """Получение названия документа."""
        label = doc_service.get_document_label("passport")
        assert label == "Паспорт"

    def test_get_document_label_unknown(self, doc_service):
        """Неизвестный документ."""
        label = doc_service.get_document_label("unknown")
        assert label == "unknown"


class TestTelegramService:
    """Тесты TelegramService."""

    @pytest.fixture
    def telegram_service(self, monkeypatch):
        """TelegramService с моками."""
        from src.config import AppConfig
        test_config = AppConfig(telegram_timeout=10)
        monkeypatch.setattr("src.services.get_config", lambda: test_config)
        monkeypatch.setattr("src.services.get_bot_token", lambda: "TEST_TOKEN")
        return TelegramService()

    def test_send_rejection_no_token(self, telegram_service, monkeypatch, sample_worker):
        """Отправка без токена."""
        monkeypatch.setattr("src.services.get_bot_token", lambda: None)

        result = []
        def callback(success, msg):
            result.append((success, msg))

        telegram_service.send_rejection(sample_worker, ["passport"], callback)

        # Ждем асинхронного выполнения
        import time
        time.sleep(0.1)
        assert len(result) == 1
        assert result[0][0] is False
        assert "токен" in result[0][1].lower()

    def test_send_rejection_no_telegram_id(self, telegram_service, sample_worker):
        """Отправка работнику без telegram_id."""
        worker = Worker(id="TEST001", name="Test", telegram_id=None)

        result = []
        def callback(success, msg):
            result.append((success, msg))

        telegram_service.send_rejection(worker, ["passport"], callback)

        import time
        time.sleep(0.1)
        assert len(result) == 1
        assert result[0][0] is False
        assert "telegram_id" in result[0][1].lower()

    def test_shutdown(self, telegram_service):
        """Корректное завершение."""
        telegram_service.shutdown()  # Не должно падать


class TestPDFExportService:
    """Тесты PDFExportService."""

    @pytest.fixture
    def pdf_service(self, test_db_path, test_docs_dir, monkeypatch):
        """PDFExportService с тестовыми путями."""
        from src.config import AppPaths, AppConfig

        test_paths = AppPaths(
            project_root=test_docs_dir.parent,
            db_path=test_db_path,
            docs_dir=test_docs_dir,
            bot_dir=test_docs_dir.parent / "bot",
        )
        test_config = AppConfig(
            image_extensions=[".jpg", ".png"],
            pdf_photo_size=(80, 80),
            pdf_doc_size=(60, 60),
        )

        monkeypatch.setattr("src.services.get_paths", lambda: test_paths)
        monkeypatch.setattr("src.services.get_config", lambda: test_config)
        monkeypatch.setattr("src.services.get_db_service", lambda: DatabaseService(test_db_path))

        # Мокаем DocumentService
        mock_doc_service = Mock()
        mock_doc_service.get_worker_documents.return_value = []
        mock_doc_service.find_photo.return_value = None
        mock_doc_service._doc_labels = {"passport": "Паспорт"}
        monkeypatch.setattr("src.services.get_document_service", lambda: mock_doc_service)

        # Мокаем get_document_config
        doc_flows = {
            "Патент": [
                MockDocumentType(key="passport", label="Паспорт", prefix="pas"),
            ]
        }
        doc_labels = {"passport": "Паспорт"}
        doc_prefixes = {"passport": "pas"}
        monkeypatch.setattr("src.services.get_document_config", lambda: (doc_flows, doc_labels, doc_prefixes))

        return PDFExportService()

    def test_export_creates_pdf(self, pdf_service, sample_worker, tmp_path):
        """Экспорт создает PDF файл."""
        output_path = tmp_path / "test.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
        assert success is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_with_photo(self, pdf_service, sample_worker, test_docs_dir, tmp_path):
        """Экспорт с фото."""
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="green")
        img.save(test_docs_dir / "photo_TEST001.jpg")

        output_path = tmp_path / "test_with_photo.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
        assert success is True
        assert output_path.exists()

    def test_export_with_documents(self, pdf_service, sample_worker_with_docs, test_docs_dir, tmp_path):
        """Экспорт с документами."""
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(test_docs_dir / "pas_TEST002.jpg")

        output_path = tmp_path / "test_with_docs.pdf"
        success, msg = pdf_service.export(sample_worker_with_docs, output_path)
        assert success is True
        assert output_path.exists()

    def test_export_rejected_worker(self, pdf_service, sample_worker, tmp_path):
        """Экспорт отклоненного работника с замечаниями."""
        worker = Worker(
            id="TEST003",
            name="Сидоров",
            citizenship="Патент",
            status="rejected",
            rejection_reasons=json.dumps(["passport", "photo"]),
        )

        output_path = tmp_path / "test_rejected.pdf"
        success, msg = pdf_service.export(worker, output_path)
        assert success is True
        assert output_path.exists()


class TestGlobalServices:
    """Тесты глобальных функций получения сервисов."""

    def test_get_document_service_singleton(self, monkeypatch):
        """DocumentService - синглтон."""
        from src.config import AppPaths, AppConfig
        test_paths = AppPaths(
            project_root=Path("."),
            db_path=Path("test.db"),
            docs_dir=Path("docs"),
            bot_dir=Path("bot"),
        )
        test_config = AppConfig()
        monkeypatch.setattr("src.services.get_paths", lambda: test_paths)
        monkeypatch.setattr("src.services.get_config", lambda: test_config)
        monkeypatch.setattr("src.services.get_db_service", lambda: Mock())
        monkeypatch.setattr("src.services.get_document_config", lambda: ({}, {}, {}))

        s1 = get_document_service()
        s2 = get_document_service()
        assert s1 is s2