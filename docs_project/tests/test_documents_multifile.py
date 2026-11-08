"""
Тесты загрузки multi-file документов (bot/handlers/documents.py).

Регресс-тест спеки 013: каждый файл multi-file документа получает уникальный temp-путь,
иначе все файлы кроме последнего перезаписываются.
"""
import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from handlers.documents import _download_document


def _run(coro):
    return asyncio.run(coro)


class TestMultiFileTempPaths:
    def test_multifile_files_get_unique_temp_paths(self, tmp_path, monkeypatch):
        """Два файла одного multi-file документа — разные temp-пути и разное содержимое."""
        docs_dir = str(tmp_path)
        monkeypatch.setattr("handlers.documents.DOCS_DIR", docs_dir)
        monkeypatch.setattr("handlers.documents.validate_file_extension", lambda p: True)

        from config.documents import DocumentType
        wb = DocumentType(key='russia_work_book', label='Трудовая книжка', prefix='trud', multi_file=True)
        monkeypatch.setattr("handlers.documents.get_doc_by_key", lambda k: wb)

        bot = AsyncMock()
        bot.get_file.return_value.file_path = "documents/file.jpg"
        counter = {"n": 0}

        async def fake_download(file_path, dest):
            counter["n"] += 1
            with open(dest, "wb") as f:
                # сигнатура JPEG — бот проверяет содержимое по magic-байтам
                f.write(b'\xff\xd8\xff\xe0' + f"CONTENT_{counter['n']}".encode())

        bot.download_file = fake_download

        message = MagicMock()
        message.from_user.id = 42
        message.answer = AsyncMock()
        message.photo = None
        message.document.file_id = "f"

        state = AsyncMock()
        state.get_data.return_value = {"temp_files": [], "citizenship": "Россия"}

        _run(_download_document(message, state, bot, "russia_work_book"))
        path1 = state.update_data.call_args.kwargs["russia_work_book_temp_paths"][0]

        state.get_data.return_value = {
            "temp_files": [path1],
            "citizenship": "Россия",
            "russia_work_book_temp_paths": [path1],
        }
        _run(_download_document(message, state, bot, "russia_work_book"))
        kwargs = state.update_data.call_args.kwargs
        paths = kwargs["russia_work_book_temp_paths"]

        assert len(paths) == 2
        assert paths[0] != paths[1]

        with open(paths[0], "rb") as f:
            c1 = f.read()[4:].decode()
        with open(paths[1], "rb") as f:
            c2 = f.read()[4:].decode()
        assert {c1, c2} == {"CONTENT_1", "CONTENT_2"}
        # temp_files — без дублей путей
        assert kwargs["temp_files"] == paths
