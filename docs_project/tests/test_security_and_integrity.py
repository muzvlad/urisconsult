"""Тесты безопасности API и целостности данных (спеки 056, 057, 058, 051, 053)."""
import os
import sys
import io
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

JPEG_BYTES = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00'


@pytest.fixture
def client(feature_db, worker_factory):
    from api_server import app

    asyncio.run(feature_db.save_worker(worker_factory()))
    return app.test_client()


class TestPathTraversal:
    """worker_id и filename из URL не должны уводить за пределы DOCS_DIR."""

    def test_delete_parent_dir_is_rejected(self, client, tmp_path, monkeypatch):
        import api_server

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        marker = docs_dir / "marker.txt"
        marker.write_text("alive")
        monkeypatch.setattr(api_server, 'DOCS_DIR', str(docs_dir))

        resp = client.delete('/api/workers/..')

        assert resp.status_code == 400
        assert marker.exists()

    def test_docs_serve_rejects_traversal(self, client, tmp_path, monkeypatch):
        import api_server

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "secret.db").write_text("private")
        monkeypatch.setattr(api_server, 'DOCS_DIR', str(docs_dir))

        assert client.get('/docs/../secret.db').status_code == 400
        assert client.get('/docs/00001/../../secret.db').status_code in (400, 404)


class TestApiToken:
    """Опциональная авторизация по заголовку X-API-Token."""

    def test_without_token_forbidden(self, client, monkeypatch):
        import api_server

        monkeypatch.setattr(api_server, 'API_TOKEN', 'secret')
        assert client.get('/api/workers').status_code == 401

    def test_with_token_allowed(self, client, monkeypatch):
        import api_server

        monkeypatch.setattr(api_server, 'API_TOKEN', 'secret')
        resp = client.get('/api/workers', headers={'X-API-Token': 'secret'})
        assert resp.status_code == 200


class TestUploadValidation:
    """Размер и тип файла проверяются на сервере."""

    def test_fake_image_rejected(self, client, tmp_path, monkeypatch):
        import api_server

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        monkeypatch.setattr(api_server, 'DOCS_DIR', str(docs_dir))

        resp = client.post('/api/workers/00001/documents', data={
            'doc_type': 'photo',
            'file': (io.BytesIO(b'this is not an image'), 'upload.jpg'),
        }, content_type='multipart/form-data')

        assert resp.status_code == 400
        assert 'jpg' in resp.get_json()['error']

    def test_new_document_creates_db_record(self, client, tmp_path, monkeypatch):
        import api_server

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        monkeypatch.setattr(api_server, 'DOCS_DIR', str(docs_dir))

        resp = client.post('/api/workers/00001/documents', data={
            'doc_type': 'photo',
            'file': (io.BytesIO(JPEG_BYTES), 'upload.jpg'),
        }, content_type='multipart/form-data')

        assert resp.status_code == 200
        docs = client.get('/api/workers/00001/documents').get_json()
        assert [d['filename'] for d in docs['photo']] == ['photo.jpg']

    def test_request_size_is_limited(self):
        from api_server import app
        from config import MAX_FILE_SIZE

        assert app.config['MAX_CONTENT_LENGTH'] > MAX_FILE_SIZE


class TestMagicBytes:
    def test_jpeg_and_text(self, tmp_path):
        from services.file_saver import FileSaver

        jpg = tmp_path / "a.jpg"
        jpg.write_bytes(JPEG_BYTES)
        assert FileSaver.check_magic(str(jpg))[0] is True

        txt = tmp_path / "b.jpg"
        txt.write_bytes(b'hello')
        ok, err = FileSaver.check_magic(str(txt))
        assert ok is False
        assert 'jpg' in err

    def test_pdf_signature(self, tmp_path):
        from services.file_saver import FileSaver

        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b'%PDF-1.7\n')
        assert FileSaver.check_magic(str(pdf))[0] is True


class TestHrStatus:
    def test_empty_date_clears_value(self, client):
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed',
                                'hr_status_date': '01.01.2026'}).status_code == 200
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'rejected',
                                'hr_status_date': ''}).status_code == 200
        assert client.get('/api/workers/00001').get_json()['hr_status_date'] == ''

    def test_employed_without_date_rejected(self, client):
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed',
                                'hr_status_date': ''}).status_code == 400


class TestDocumentHistory:
    """created_at первой загрузки не сбрасывается (спека 051)."""

    def test_created_at_preserved_on_reupload(self, feature_db, worker_factory):
        asyncio.run(feature_db.save_worker(worker_factory()))
        asyncio.run(feature_db.save_documents('00001', {'photo': 'photo.jpg'}))
        first = asyncio.run(feature_db.get_worker_documents('00001'))['photo'][0]['created_at']

        asyncio.run(feature_db.save_documents('00001', {'photo': 'photo.jpg'}))
        second = asyncio.run(feature_db.get_worker_documents('00001'))['photo'][0]['created_at']

        assert first == second

    def test_add_document_is_not_duplicated(self, feature_db, worker_factory):
        asyncio.run(feature_db.save_worker(worker_factory()))
        assert asyncio.run(feature_db.add_document('00001', 'photo', 'photo.jpg')) is True
        assert asyncio.run(feature_db.add_document('00001', 'photo', 'photo.jpg')) is False
        docs = asyncio.run(feature_db.get_worker_documents('00001'))
        assert len(docs['photo']) == 1


class TestListColumns:
    """Списочные выборки не тянут тяжёлые JSON (спека 053)."""

    def test_relatives_json_not_returned(self, feature_db, worker_factory):
        asyncio.run(feature_db.save_worker(
            worker_factory(relatives_json=json.dumps([{'name': 'Иванов'}]))))

        workers = asyncio.run(feature_db.get_all_workers())

        assert 'relatives_json' not in workers[0]
        assert workers[0]['rejection_reasons'] == '[]'

    def test_get_worker_returns_full_record(self, feature_db, worker_factory):
        asyncio.run(feature_db.save_worker(
            worker_factory(relatives_json=json.dumps([{'name': 'Иванов'}]))))

        worker = asyncio.run(feature_db.get_worker('00001'))

        assert worker['relatives_json']


class TestSaveWorkerKeepsAbsentFields:
    def test_partial_update_does_not_wipe(self, feature_db, worker_factory):
        asyncio.run(feature_db.save_worker(worker_factory(registration='Рег. № 123')))

        asyncio.run(feature_db.save_worker({'id': '00001', 'name': 'Иванов Иван Иванович'}))

        worker = asyncio.run(feature_db.get_worker('00001'))
        assert worker['registration'] == 'Рег. № 123'
        assert worker['name'] == 'Иванов Иван Иванович'


class TestFixRejectedKeepsAllFields:
    """Исправление анкеты не затирает registration, семейное положение и родственников."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_all_fields_copied_to_state(self, monkeypatch):
        from handlers.commands import handle_rejected_callback
        from services.fsm_storage import SQLiteStorage
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.storage.base import StorageKey

        worker = {
            'id': '00001',
            'name': 'Иванов Иван Иванович',
            'citizenship': 'Россия',
            'registration': 'Рег. № 123',
            'marital_status': 'Женат/Замужем',
            'relatives_json': json.dumps([{'name': 'Пётр', 'birth_year': '1985',
                                           'phone': '+79990000000'}]),
            'rejection_reasons': '[]',
        }

        async def fake_get_worker(worker_id):
            return worker
        monkeypatch.setattr("handlers.commands.db.get_worker", fake_get_worker)

        storage = SQLiteStorage(":memory:")
        state = FSMContext(storage=storage, key=StorageKey(
            bot_id=1, chat_id=111, user_id=111, thread_id=None))

        message = MagicMock()
        message.answer = AsyncMock()
        message.edit_text = AsyncMock()
        callback = MagicMock()
        callback.data = "fix_rejected:00001"
        callback.message = message
        callback.answer = AsyncMock()

        self._run(handle_rejected_callback(callback, state))

        data = self._run(state.get_data())
        assert data['registration'] == 'Рег. № 123'
        assert data['russia_marital_status'] == 'Женат/Замужем'
        assert data['russia_relatives_list'][0]['name'] == 'Пётр'
        self._run(storage.close())


class TestNewRejectedDoesNotDuplicate:
    """«Новая анкета» не переводит отклонённую запись в pending (спека 058)."""

    def test_worker_stays_rejected(self, monkeypatch):
        from handlers.commands import handle_rejected_callback
        from services.fsm_storage import SQLiteStorage
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.storage.base import StorageKey

        calls = []

        async def fake_resubmit(worker_id):
            calls.append(worker_id)
        monkeypatch.setattr("handlers.commands.db.resubmit_worker", fake_resubmit)

        storage = SQLiteStorage(":memory:")
        state = FSMContext(storage=storage, key=StorageKey(
            bot_id=1, chat_id=111, user_id=111, thread_id=None))

        message = MagicMock()
        message.answer = AsyncMock()
        message.edit_text = AsyncMock()
        callback = MagicMock()
        callback.data = "new_rejected:00001"
        callback.message = message
        callback.answer = AsyncMock()

        asyncio.run(handle_rejected_callback(callback, state))

        assert calls == []
        self_state = asyncio.run(state.get_state())
        from handlers.registration import get_worker_form
        assert self_state == get_worker_form().name.state
        asyncio.run(storage.close())


class TestTextOnlyStates:
    """Текстовые поля принимают только текст (спека 057)."""

    def test_text_handlers_filter_by_text(self):
        from aiogram import Dispatcher
        from handlers.registration import (register_registration_handlers,
                                           get_worker_form, process_name)

        dp = Dispatcher()
        register_registration_handlers(dp, get_worker_form())

        handlers = [h for h in dp.message.handlers if h.callback is process_name]
        assert handlers, 'process_name не зарегистрирован'

        magic_filters = [f.magic for f in handlers[0].filters if f.magic is not None]
        assert magic_filters, 'нет фильтра F.text'

        photo = MagicMock()
        photo.text = None
        photo.photo = [object()]
        assert not magic_filters[0].resolve(photo)

        text = MagicMock()
        text.text = 'Иванов Иван'
        assert magic_filters[0].resolve(text)

    def test_expect_text_registered_for_text_states(self):
        from aiogram import Dispatcher
        from aiogram.filters import StateFilter
        from handlers.registration import (register_registration_handlers,
                                           get_worker_form, expect_text, TEXT_FIELDS)

        dp = Dispatcher()
        WorkerForm = get_worker_form()
        register_registration_handlers(dp, WorkerForm)

        handlers = [h for h in dp.message.handlers if h.callback is expect_text]
        assert handlers, 'expect_text не зарегистрирован'

        states = [getattr(WorkerForm, name) for name in TEXT_FIELDS]
        state_filter = handlers[0].filters[0]
        assert isinstance(state_filter.callback, StateFilter)
        assert asyncio.run(state_filter.callback(WorkerForm.name,
                                                raw_state=WorkerForm.name.state))


class TestThrottleMedia:

    def test_media_does_not_hit_limit(self):
        import time
        from middleware import ThrottlingMiddleware

        middleware = ThrottlingMiddleware(rate_limit=2, period=10.0)
        handler = AsyncMock(return_value="ok")

        async def send(i):
            event = MagicMock()
            event.from_user.id = 1
            event.photo = [object()]
            event.document = None
            event.answer = AsyncMock()
            return await middleware(handler, event, {})

        for i in range(5):
            assert asyncio.run(send(i)) == "ok"

        # Текстовые сообщения по-прежнему ограничиваются
        event = MagicMock()
        event.from_user.id = 1
        event.photo = None
        event.document = None
        event.answer = AsyncMock()
        asyncio.run(middleware(handler, event, {}))
        asyncio.run(middleware(handler, event, {}))
        assert asyncio.run(middleware(handler, event, {})) is None
