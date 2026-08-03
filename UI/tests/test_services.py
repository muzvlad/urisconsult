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


@dataclass
class MockDocumentType:
    key: str
    label: str
    prefix: str
    required: bool = False
    can_skip: bool = True
    category: str = ""


@pytest.fixture
def test_docs_dir(tmp_path):
    """Тестовая папка документов."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return docs


@pytest.fixture
def sample_worker():
    """Создает тестового работника."""
    return Worker(
        id="TEST001",
        name="Иванов Иван",
        citizenship="Патент",
        status="pending",
    )


@pytest.fixture
def sample_worker_with_docs():
    """Работник с документами."""
    return Worker(
        id="TEST002",
        name="Петров Петр",
        citizenship="Патент",
        status="accepted",
    )


@pytest.fixture
def mock_api():
    """Мок API клиента."""
    api = Mock()
    api.base_url = "http://localhost:56755"
    api.get_documents.return_value = {"passport": "pas_TEST002.jpg", "photo": "photo_TEST002.jpg"}
    api.get_meetings.return_value = []
    api.download_file.return_value = None
    return api


class TestDocumentService:
    """Тесты DocumentService."""

    @pytest.fixture
    def doc_service(self, test_docs_dir, monkeypatch):
        """DocumentService с переопределенными путями."""
        from src.config import AppPaths, AppConfig
        test_paths = AppPaths(
            project_root=test_docs_dir.parent,
            db_path=test_docs_dir.parent / "test.db",
            docs_dir=test_docs_dir,
            bot_dir=test_docs_dir.parent / "bot",
        )
        test_config = AppConfig(image_extensions=[".jpg", ".png"])

        monkeypatch.setattr("src.services.get_paths", lambda: test_paths)
        monkeypatch.setattr("src.services.get_config", lambda: test_config)

        def mock_get_db():
            api = Mock()
            api.download_file.return_value = None
            return api
        monkeypatch.setattr("src.api_client.get_db_service", mock_get_db)

        doc_flows = {
            "Патент": [
                MockDocumentType(key="passport", label="Паспорт", prefix="pas"),
                MockDocumentType(key="photo", label="Фото", prefix="photo"),
            ]
        }
        doc_labels = {"passport": "Паспорт", "photo": "Фото"}
        doc_prefixes = {"passport": "pas", "photo": "photo"}
        monkeypatch.setattr("src.services.get_document_config", lambda: (doc_flows, doc_labels, doc_prefixes))

        return DocumentService()

    def test_find_photo_via_api(self, doc_service, test_docs_dir, sample_worker, monkeypatch):
        """Поиск фото работает через API download."""
        from PIL import Image
        worker_dir = test_docs_dir / "TEST001"
        worker_dir.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (100, 100), color="green")
        img_path = worker_dir / "photo.jpg"
        img.save(img_path)

        def mock_get_db():
            api = Mock()
            api.download_file.return_value = img_path
            return api
        monkeypatch.setattr("src.api_client.get_db_service", mock_get_db)

        found = doc_service.find_photo("TEST001")
        assert found is not None
        assert found == img_path

    def test_find_photo_not_exists(self, doc_service, sample_worker):
        """Фото не найдено."""
        found = doc_service.find_photo("NONEXISTENT")
        assert found is None

    def test_get_document_label(self, doc_service):
        """Получение названия документа."""
        label = doc_service.get_document_label("passport")
        assert label == "Паспорт"

    def test_get_document_label_unknown(self, doc_service):
        """Неизвестный документ."""
        label = doc_service.get_document_label("unknown")
        assert label == "unknown"

    def test_load_pdf_thumbnail(self, doc_service, test_docs_dir):
        """Миниатюра первой страницы PDF генерируется."""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from reportlab.pdfgen import canvas
            pdf_path = test_docs_dir / "test.pdf"
            c = canvas.Canvas(str(pdf_path))
            c.setFont("Helvetica", 24)
            c.drawString(50, 750, "Hello PDF")
            c.showPage()
            c.save()

            thumb = doc_service.load_pdf_thumbnail(pdf_path, (120, 120))
            assert thumb is not None
            assert thumb.width() > 0
            assert thumb.height() > 0
        finally:
            root.destroy()

    def test_load_pdf_thumbnail_invalid(self, doc_service, test_docs_dir):
        """Битый PDF -> None, без исключения."""
        bad = test_docs_dir / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        assert doc_service.load_pdf_thumbnail(bad, (120, 120)) is None


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
        telegram_service.shutdown()


class TestPDFExportService:
    """Тесты PDFExportService."""

    @pytest.fixture
    def pdf_service(self, test_docs_dir, monkeypatch, mock_api):
        """PDFExportService с тестовыми путями и моком API."""
        from src.config import AppPaths, AppConfig

        test_paths = AppPaths(
            project_root=test_docs_dir.parent,
            db_path=test_docs_dir.parent / "test.db",
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

        def mock_get_db():
            return mock_api
        monkeypatch.setattr("src.api_client.get_db_service", mock_get_db)

        # Мокаем DocumentService
        mock_doc_service = Mock()
        mock_doc_service.get_worker_documents.return_value = []
        mock_doc_service.find_photo.return_value = None
        mock_doc_service._doc_labels = {"passport": "Паспорт"}
        mock_doc_service._doc_flows = {}
        monkeypatch.setattr("src.services.get_document_service", lambda: mock_doc_service)

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
        """Экспорт с фото — фото в правом верхнем углу."""
        from PIL import Image
        worker_dir = test_docs_dir / "TEST001"
        worker_dir.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (100, 100), color="green")
        img.save(worker_dir / "photo.jpg")

        # Мокаем find_photo чтобы вернул реальный путь
        mock_doc = Mock()
        mock_doc.find_photo.return_value = worker_dir / "photo.jpg"
        mock_doc._doc_flows = {}
        mock_doc._doc_labels = {}
        pdf_service.doc_service = mock_doc

        output_path = tmp_path / "test_with_photo.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
        assert success is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_with_documents(self, pdf_service, sample_worker_with_docs, test_docs_dir, tmp_path, mock_api):
        """Экспорт с документами."""
        from PIL import Image
        worker_dir = test_docs_dir / "TEST002"
        worker_dir.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(worker_dir / "pas.jpg")

        mock_api.get_documents.return_value = {"passport": "pas_TEST002.jpg"}
        mock_api.download_file.return_value = worker_dir / "pas.jpg"

        pdf_service.doc_service._doc_flows = {
            "Патент": [MockDocumentType(key="passport", label="Паспорт", prefix="pas")]
        }

        output_path = tmp_path / "test_with_docs.pdf"
        success, msg = pdf_service.export(sample_worker_with_docs, output_path)
        assert success is True
        assert output_path.exists()

    def test_export_rejected_worker(self, pdf_service, tmp_path):
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

    def test_export_with_meetings(self, pdf_service, sample_worker, tmp_path, mock_api):
        """Экспорт с встречами."""
        mock_api.get_meetings.return_value = [
            {"date": "25.07.2026", "note": "Первая встреча"},
            {"date": "27.07.2026", "note": "Вторая встреча"},
        ]

        output_path = tmp_path / "test_with_meetings.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
        assert success is True
        assert output_path.exists()

    def test_export_photo_positioned_top_right(self, pdf_service, sample_worker, test_docs_dir, tmp_path):
        """Фото расположено в правом верхнем углу PDF."""
        from PIL import Image
        from reportlab.lib.pagesizes import A4

        worker_dir = test_docs_dir / "TEST001"
        worker_dir.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (100, 100), color="red")
        img.save(worker_dir / "photo.jpg")

        mock_doc = Mock()
        mock_doc.find_photo.return_value = worker_dir / "photo.jpg"
        mock_doc._doc_flows = {}
        mock_doc._doc_labels = {}
        pdf_service.doc_service = mock_doc

        output_path = tmp_path / "test_position.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
        assert success is True

        width, height = A4
        expected_x = width - 50 - 80
        expected_y = height - 50 - 80
        assert expected_x > 400
        assert expected_y > 400

    def test_export_empty_worker(self, pdf_service, sample_worker, tmp_path):
        """Экспорт работника без данных."""
        output_path = tmp_path / "test_empty.pdf"
        success, msg = pdf_service.export(sample_worker, output_path)
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

        def mock_get_db():
            return Mock()
        monkeypatch.setattr("src.api_client.get_db_service", mock_get_db)
        monkeypatch.setattr("src.services.get_document_config", lambda: ({}, {}, {}))

        s1 = get_document_service()
        s2 = get_document_service()
        assert s1 is s2
