"""
Фикстуры для тестов URIS Consult.

Запуск: cd docs_project && python -m pytest tests/ -v
"""
import os
import sys
import sqlite3
import tempfile
import shutil
import asyncio
import pytest

# Добавляем bot/ в путь для импорта конфига
BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)


@pytest.fixture
def tmp_docs_dir(tmp_path):
    """Временная папка для документов."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return str(docs)


@pytest.fixture
def tmp_db_path(tmp_path):
    """Путь к временной SQLite БД."""
    return str(tmp_path / "test_users.db")


@pytest.fixture
def sample_worker_data():
    """Тестовые данные работника."""
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
def sample_worker_data_russia():
    """Тестовые данные работника (Россия)."""
    return {
        'id': '00002',
        'name': 'Сидоров Пётр Васильевич',
        'citizenship': 'Россия',
        'gender': 'Мужской',
        'position': 'Слесарь',
        'object': 'Офис',
        'object_address': 'ул. Ленина, д. 5',
        'manager': 'Козлов К.К.',
        'phone_main': '+79997654321',
        'phone_additional': 'Не указан',
        'email': 'sidorov@test.com',
        'date': '15.06.1985',
    }


@pytest.fixture
def in_memory_db():
    """Создание БД в памяти для тестов."""
    import aiosqlite

    class InMemoryDB:
        def __init__(self):
            self._db = None

        async def connect(self):
            self._db = await aiosqlite.connect(":memory:")
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA foreign_keys=ON")
            return self._db

        async def close(self):
            if self._db:
                await self._db.close()

    return InMemoryDB()
