"""Тесты мягкого архива и фильтрации (spec 028)."""
import asyncio
import sqlite3


class TestArchive:
    def test_archive_unarchive_and_filters(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory('00001')))
        asyncio.run(db.save_worker(worker_factory('00002', name='Петров Пётр')))

        assert asyncio.run(db.archive_worker('00001')) is True

        active = asyncio.run(db.get_all_workers('0'))
        archived = asyncio.run(db.get_all_workers('1'))
        every = asyncio.run(db.get_all_workers('all'))
        assert [w['id'] for w in active] == ['00002']
        assert [w['id'] for w in archived] == ['00001']
        assert {w['id'] for w in every} == {'00001', '00002'}
        assert archived[0]['archived_at']

        assert asyncio.run(db.get_workers_by_status('pending', '1'))[0]['id'] == '00001'
        assert asyncio.run(db.search_workers('Петров', '0'))[0]['id'] == '00002'
        assert asyncio.run(db.search_workers('Иванов', '0')) == []

        assert asyncio.run(db.unarchive_worker('00001')) is True
        assert [w['id'] for w in asyncio.run(db.get_all_workers('0'))] == ['00001', '00002']

    def test_pending_count_excludes_archive_and_notifications_skip_it(
            self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory('00001')))
        asyncio.run(db.save_worker(worker_factory('00002', name='Петров Пётр')))
        asyncio.run(db.add_meeting('00001', '01.01.2026', ''))
        asyncio.run(db.add_meeting('00002', '01.01.2026', ''))

        assert asyncio.run(db.get_pending_count()) == 2
        asyncio.run(db.archive_worker('00001'))
        assert asyncio.run(db.get_pending_count()) == 1
        assert [m['worker_id'] for m in asyncio.run(db.get_unnotified_meetings())] == ['00002']

    def test_resubmit_clears_archive(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory()))
        asyncio.run(db.reject_worker('00001', ['passport']))
        asyncio.run(db.archive_worker('00001'))

        asyncio.run(db.resubmit_worker('00001'))
        worker = asyncio.run(db.get_worker('00001'))
        assert worker['status'] == 'pending'
        assert not worker['archived_at']

    def test_date_filter_uses_created_at(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory('00001')))
        asyncio.run(db.save_worker(worker_factory('00002', name='Петров Пётр')))

        conn = sqlite3.connect(db.DB_PATH)
        conn.execute("UPDATE workers SET created_at = '2026-01-10T10:00:00' WHERE id = '00001'")
        conn.execute("UPDATE workers SET created_at = '2026-02-10T10:00:00' WHERE id = '00002'")
        conn.commit()
        conn.close()

        january = asyncio.run(db.get_all_workers('0', '2026-01-01', '2026-01-31'))
        assert [w['id'] for w in january] == ['00001']
