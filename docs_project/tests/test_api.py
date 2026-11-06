"""Тесты HTTP API (spec 025, 027, 035, 036)."""
import asyncio
import io
import os
import sys

import pytest

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)


@pytest.fixture
def client(feature_db, worker_factory):
    from api_server import app

    asyncio.run(feature_db.save_worker(worker_factory()))
    return app.test_client()


class TestWorkersApi:
    def test_customer_legal_entity_and_archive(self, client):
        assert client.get('/api/workers').get_json()[0]['customer'] == 'ООО Ромашка'

        resp = client.put('/api/workers/00001/legal-entity', json={'legal_entity': 'ООО Тест'})
        assert resp.status_code == 200
        assert client.get('/api/workers/00001').get_json()['legal_entity'] == 'ООО Тест'

        assert client.post('/api/workers/00001/archive').status_code == 200
        assert client.get('/api/workers?archived=0').get_json() == []
        assert len(client.get('/api/workers?archived=1').get_json()) == 1
        assert len(client.get('/api/workers?archived=all').get_json()) == 1
        assert client.post('/api/workers/00001/unarchive').status_code == 200
        assert len(client.get('/api/workers').get_json()) == 1

    def test_date_filters_are_validated(self, client):
        assert client.get('/api/workers?date_from=2026-01-01&date_to=2026-01-31').status_code == 200
        assert client.get('/api/workers?date_from=01.01.2026').status_code == 400
        assert client.get('/api/workers?date_from=2026-1-1').status_code == 400
        assert client.get('/api/workers?date_to=2026-13-01').status_code == 400
        assert client.get('/api/workers?archived=bad').status_code == 400


class TestHrStatusApi:
    def test_employed_requires_date(self, client):
        # employed требует дату — без даты 400
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed'}).status_code == 400
        # невалидный формат даты — 400
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed',
                                'hr_status_date': '1.1.2026'}).status_code == 400
        # оба формата даты допустимы (ДД.ММ.ГГГГ и YYYY-MM-DD)
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed',
                                'hr_status_date': '2026-01-01'}).status_code == 200
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'employed',
                                'hr_status_date': '01.01.2026'}).status_code == 200
        worker = client.get('/api/workers/00001').get_json()
        assert worker['hr_status'] == 'employed'
        assert worker['hr_status_date'] == '01.01.2026'

    def test_invalid_status_and_date_cleared(self, client):
        assert client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'unknown'}).status_code == 400

        resp = client.put('/api/workers/00001/hr-status',
                          json={'hr_status': 'rejected', 'hr_status_date': '01.01.2026'})
        assert resp.status_code == 200
        # Дата сохраняется для любого статуса, не очищается
        assert client.get('/api/workers/00001').get_json()['hr_status_date'] == '01.01.2026'


class TestDocumentsSignedApi:
    def test_documents_signed_toggle(self, client):
        # По умолчанию не подписаны
        worker = client.get('/api/workers/00001').get_json()
        assert worker.get('documents_signed') == '0'

        # Подписать
        resp = client.put('/api/workers/00001/documents-signed',
                          json={'documents_signed': '1'})
        assert resp.status_code == 200
        assert client.get('/api/workers/00001').get_json()['documents_signed'] == '1'

        # Снять галочку
        resp = client.put('/api/workers/00001/documents-signed',
                          json={'documents_signed': '0'})
        assert resp.status_code == 200
        assert client.get('/api/workers/00001').get_json()['documents_signed'] == '0'

        # Неверное значение — 404 (rowcount 0) или 200 с False? set_documents_signed
        # возвращает False для не '0'/'1' -> api отдаст 404
        resp = client.put('/api/workers/00001/documents-signed',
                          json={'documents_signed': '2'})
        assert resp.status_code == 404


class TestNotesAndMeetingsApi:
    def test_notes_crud(self, client):
        created = client.post('/api/workers/00001/notes', json={'text': '  Заметка  '})
        assert created.status_code == 200
        note_id = created.get_json()['id']

        notes = client.get('/api/workers/00001/notes').get_json()
        assert notes[0]['text'] == 'Заметка'
        assert client.post('/api/workers/00001/notes', json={'text': '   '}).status_code == 400

        assert client.put(f'/api/workers/00001/notes/{note_id}',
                          json={'text': 'Новая'}).status_code == 200
        assert client.get('/api/workers/00001/notes').get_json()[0]['text'] == 'Новая'
        assert client.delete(f'/api/workers/00001/notes/{note_id}').status_code == 200
        assert client.get('/api/workers/00001/notes').get_json() == []

    def test_meeting_date_validation(self, client):
        assert client.post('/api/workers/00001/meetings',
                           json={'date': '26.10.2026 14:30'}).status_code == 200
        assert client.post('/api/workers/00001/meetings',
                           json={'date': '26/10/2026'}).status_code == 400
        assert client.post('/api/workers/00001/meetings',
                           json={'date': '26.10.2026 9:30'}).status_code == 400

    def test_list_meetings_returns_same_shape(self, client):
        """GET meetings отдаёт id, date, note, created_at (spec 035)."""
        client.post('/api/workers/00001/meetings',
                    json={'date': '26.10.2026 14:30', 'note': 'Планёрка'})

        meetings = client.get('/api/workers/00001/meetings').get_json()
        assert len(meetings) == 1
        assert set(meetings[0]) == {'id', 'date', 'note', 'created_at'}
        assert meetings[0]['date'] == '26.10.2026 14:30'
        assert meetings[0]['note'] == 'Планёрка'


class TestDocumentsApi:
    def test_replace_document_overwrites_file_and_keeps_record(self, client, feature_db,
                                                               tmp_path, monkeypatch):
        """Перезаливка из UI: файл перезаписан под тем же именем, запись остаётся (spec 036)."""
        import api_server

        docs_dir = tmp_path / "api_docs"
        docs_dir.mkdir()
        monkeypatch.setattr(api_server, 'DOCS_DIR', str(docs_dir))

        asyncio.run(feature_db.save_documents('00001', {'photo': 'passport.jpg'}))
        before = client.get('/api/workers/00001/documents').get_json()['photo'][0]['created_at']

        worker_dir = docs_dir / '00001'
        worker_dir.mkdir()
        target = worker_dir / 'passport.jpg'
        target.write_bytes(b'old-content')

        resp = client.post('/api/workers/00001/documents', data={
            'doc_type': 'photo',
            'old_filename': 'passport.jpg',
            'file': (io.BytesIO(b'new-content'), 'upload.jpg'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

        assert target.read_bytes() == b'new-content'

        docs = client.get('/api/workers/00001/documents').get_json()
        assert [d['filename'] for d in docs['photo']] == ['passport.jpg']
        assert docs['photo'][0]['created_at'] != before
