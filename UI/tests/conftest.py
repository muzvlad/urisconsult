"""
Pytest конфигурация и фикстуры для тестов.
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path
import pytest

# Добавляем src в путь
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="session")
def temp_dir():
    """Временная директория для тестов."""
    tmp = Path(tempfile.mkdtemp(prefix="urisconsult_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_db_path(temp_dir):
    """Путь к тестовой БД."""
    return temp_dir / "test_users.db"


@pytest.fixture
def test_docs_dir(temp_dir):
    """Путь к тестовой папке документов."""
    docs = temp_dir / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    return docs


@pytest.fixture
def sample_worker():
    """Пример работника для тестов."""
    from src.models import Worker
    return Worker(
        id="TEST001",
        name="Иванов Иван Иванович",
        citizenship="Патент",
        gender="М",
        position="Водитель",
        object="Объект 1",
        object_address="ул. Тестовая, 1",
        manager="Петров П.П.",
        phone_main="+79001234567",
        phone_additional="",
        email="test@example.com",
        date="01.01.1990",
        registration="г. Москва",
        marital_status="Женат",
        relatives_json='[]',
        telegram_id=123456789,
        telegram_username="testuser",
        created_at="2024-01-01T00:00:00",
        status="pending",
        rejection_reasons="[]",
    )