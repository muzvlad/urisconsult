"""Тесты встреч, разбора даты и флагов уведомлений (spec 023)."""
import asyncio
import os
import sys

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from utils import parse_meeting_datetime


class TestParseMeetingDatetime:
    def test_iso(self):
        assert parse_meeting_datetime('2026-10-26 14:30:00').strftime('%d.%m.%Y %H:%M') == '26.10.2026 14:30'

    def test_user_formats(self):
        assert parse_meeting_datetime('26.10.2026 14:30').strftime('%H:%M') == '14:30'
        assert parse_meeting_datetime('26.10.2026').strftime('%H:%M') == '00:00'

    def test_invalid(self):
        assert parse_meeting_datetime('26/10/2026') is None
        assert parse_meeting_datetime('') is None
        assert parse_meeting_datetime(None) is None


class TestMeetingFlags:
    def test_notify_then_remind(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory(telegram_id=123)))

        meeting_id = asyncio.run(db.add_meeting('00001', '01.01.2099 10:00', 'офис'))
        assert [m['id'] for m in asyncio.run(db.get_unnotified_meetings())] == [meeting_id]
        assert asyncio.run(db.get_meetings_to_remind()) == []

        asyncio.run(db.mark_meeting_notified(meeting_id, '2026-01-01T00:00:00'))
        assert asyncio.run(db.get_unnotified_meetings()) == []
        assert [m['id'] for m in asyncio.run(db.get_meetings_to_remind())] == [meeting_id]

        asyncio.run(db.mark_meeting_reminded(meeting_id, '2026-01-01T00:00:00'))
        assert asyncio.run(db.get_meetings_to_remind()) == []

    def test_archived_worker_meetings_ignored(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory(telegram_id=123)))
        asyncio.run(db.add_meeting('00001', '01.01.2099', ''))
        asyncio.run(db.archive_worker('00001'))
        assert asyncio.run(db.get_unnotified_meetings()) == []

    def test_task_sends_once_and_marks_skipped(self, feature_db, worker_factory):
        from bot import check_meeting_notifications

        db = feature_db
        asyncio.run(db.save_worker(worker_factory('00001', telegram_id=123)))
        asyncio.run(db.save_worker(worker_factory('00002', name='Петров Пётр')))
        asyncio.run(db.save_worker(worker_factory('00003', name='Сидоров',
                                                  telegram_id=456)))
        asyncio.run(db.add_meeting('00001', '01.01.2099 10:00', ''))
        asyncio.run(db.add_meeting('00002', '01.01.2099 10:00', ''))
        asyncio.run(db.add_meeting('00003', '01.01.2099 10:00', ''))
        asyncio.run(db.archive_worker('00003'))

        sent = []

        class FakeBot:
            async def send_message(self, chat_id, text):
                sent.append((chat_id, text))

        async def run_once():
            task = asyncio.create_task(check_meeting_notifications(FakeBot()))
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())
        assert [chat_id for chat_id, _ in sent] == [123]
        assert 'Вам назначена встреча' in sent[0][1]

        async def all_rows():
            async with db._get_conn() as conn:
                cur = await conn.execute(
                    "SELECT worker_id, notified_at, reminded_at FROM worker_meetings ORDER BY id")
                return [dict(r) for r in await cur.fetchall()]
        by_worker = {r['worker_id']: r for r in asyncio.run(all_rows())}
        assert by_worker['00001']['notified_at'] and not by_worker['00001']['reminded_at']
        assert by_worker['00002']['notified_at'] == 'no_telegram'
        assert by_worker['00002']['reminded_at'] == 'no_telegram'
        assert by_worker['00003']['notified_at'] is None

        asyncio.run(run_once())
        assert len(sent) == 1

    def test_meeting_within_24h_gets_no_duplicate_reminder(self, feature_db,
                                                          worker_factory):
        from datetime import datetime, timedelta
        from bot import check_meeting_notifications

        db = feature_db
        asyncio.run(db.save_worker(worker_factory(telegram_id=123)))
        soon = (datetime.now() + timedelta(hours=1)).strftime('%d.%m.%Y %H:%M')
        asyncio.run(db.add_meeting('00001', soon, ''))

        sent = []

        class FakeBot:
            async def send_message(self, chat_id, text):
                sent.append(text)

        async def run_once():
            task = asyncio.create_task(check_meeting_notifications(FakeBot()))
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())
        assert len(sent) == 1

        async def row():
            async with db._get_conn() as conn:
                cur = await conn.execute(
                    "SELECT notified_at, reminded_at FROM worker_meetings")
                return dict(await cur.fetchone())
        flags = asyncio.run(row())
        assert flags['notified_at'] and flags['reminded_at']

    def test_backfill_marks_existing_meetings(self, feature_db, worker_factory):
        db = feature_db
        asyncio.run(db.save_worker(worker_factory(telegram_id=123)))
        meeting_id = asyncio.run(db.add_meeting('00001', '01.01.2099', ''))

        async def reset_and_migrate():
            async with db._get_conn() as conn:
                await conn.execute(
                    "UPDATE worker_meetings SET notified_at = NULL, reminded_at = NULL WHERE id = ?",
                    (meeting_id,)
                )
                await conn.commit()
                await db._migrate_v5_to_v6(conn)

        asyncio.run(reset_and_migrate())
        assert asyncio.run(db.get_unnotified_meetings()) == []
        assert asyncio.run(db.get_meetings_to_remind()) == []
