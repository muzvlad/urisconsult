"""Тесты комментариев к анкете (spec 024)."""
import asyncio


class TestWorkerNotes:
    def test_crud_and_empty_text(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory()))

        assert asyncio.run(db.add_worker_note('00001', '   ')) is None
        note_id = asyncio.run(db.add_worker_note('00001', '  Первый  '))
        assert note_id

        notes = asyncio.run(db.get_worker_notes('00001'))
        assert [n['text'] for n in notes] == ['Первый']

        assert asyncio.run(db.update_worker_note(note_id, 'Второй')) is True
        assert asyncio.run(db.update_worker_note(note_id, '   ')) is False
        notes = asyncio.run(db.get_worker_notes('00001'))
        assert notes[0]['text'] == 'Второй'

        assert asyncio.run(db.delete_worker_note(note_id)) is True
        assert asyncio.run(db.get_worker_notes('00001')) == []

    def test_order_by_id_and_worker_scope(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory('00001')))
        asyncio.run(db.save_worker(worker_factory('00002', name='Петров Пётр')))

        first = asyncio.run(db.add_worker_note('00001', 'A'))
        second = asyncio.run(db.add_worker_note('00001', 'B'))
        foreign = asyncio.run(db.add_worker_note('00002', 'C'))

        assert [n['text'] for n in asyncio.run(db.get_worker_notes('00001'))] == ['A', 'B']
        assert first < second
        assert asyncio.run(db.update_worker_note(foreign, 'X', '00001')) is False
        assert asyncio.run(db.delete_worker_note(foreign, '00001')) is False

    def test_deleting_worker_cascades_notes(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory()))
        asyncio.run(db.add_worker_note('00001', 'A'))
        asyncio.run(db.add_meeting('00001', '01.01.2026', ''))

        assert asyncio.run(db.delete_worker('00001')) is True
        assert asyncio.run(db.get_worker_notes('00001')) == []
        assert asyncio.run(db.get_unnotified_meetings()) == []
