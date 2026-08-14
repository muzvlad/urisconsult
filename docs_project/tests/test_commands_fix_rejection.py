"""
Тесты исправления анкеты по отклонённым полям (bot/handlers/commands.py).

Регресс-тесты:
- `_ask_rejected_field` для документа не должен падать с NameError
  (отсутствовал импорт get_skip_keyboard).
- `handle_rejected_callback` не должен падать с NameError
  (отсутствовал импорт parse_rejection_reasons) — кнопка «Исправить анкету» молчала.
"""
import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from handlers.commands import _ask_rejected_field, handle_rejected_callback
from handlers.registration import get_worker_form
from config.documents import get_doc_by_key
from services.fsm_storage import SQLiteStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey


def _run_async(coro):
    return asyncio.run(coro)


class TestAskRejectedField:
    def test_document_field_asks_for_file(self):
        """Документ (ИНН) запрашивает исправленный файл, не падает с NameError."""
        WorkerForm = get_worker_form()
        assert hasattr(WorkerForm, 'patent_inn')

        message = MagicMock()
        message.answer = AsyncMock()
        state = MagicMock()
        state.set_state = AsyncMock()
        state.update_data = AsyncMock()

        _run_async(_ask_rejected_field(message, state, 'patent_inn', ['patent_inn'], 0))

        args, kwargs = message.answer.await_args
        assert 'Отправьте исправленный файл' in args[0]
        assert 'ИНН' in args[0]

    def test_document_field_shows_comment(self):
        """Комментарий причины отображается в запросе исправления."""
        message = MagicMock()
        message.answer = AsyncMock()
        state = MagicMock()
        state.set_state = AsyncMock()
        state.update_data = AsyncMock()

        reasons = [{'key': 'patent_inn', 'comment': 'Номер не читается'}]
        _run_async(_ask_rejected_field(message, state, 'patent_inn', reasons, 0))

        args, kwargs = message.answer.await_args
        assert 'Номер не читается' in args[0]

    def test_text_field_shows_comment(self):
        """Комментарий текстового поля отображается в запросе."""
        message = MagicMock()
        message.answer = AsyncMock()
        state = MagicMock()
        state.set_state = AsyncMock()
        state.update_data = AsyncMock()

        reasons = [{'key': 'name', 'comment': 'Опечатка в фамилии'}]
        _run_async(_ask_rejected_field(message, state, 'name', reasons, 0))

        args, kwargs = message.answer.await_args
        assert 'Опечатка в фамилии' in args[0]

    def test_text_field_asks_prompt(self):
        """Текстовое поле (ФИО) запрашивает ввод."""
        message = MagicMock()
        message.answer = AsyncMock()
        state = MagicMock()
        state.set_state = AsyncMock()
        state.update_data = AsyncMock()

        _run_async(_ask_rejected_field(message, state, 'name', ['name'], 0))

        args, kwargs = message.answer.await_args
        assert 'ФИО' in args[0]

    def test_all_doc_keys_have_states(self):
        """Каждый отклоняемый документ имеет FSM-состояние."""
        from utils import get_all_doc_keys
        WorkerForm = get_worker_form()
        for key in get_all_doc_keys():
            assert hasattr(WorkerForm, key), f"Нет состояния для документа '{key}'"

    def test_inn_labels(self):
        """ИНН во всех категориях имеет label 'ИНН'."""
        for key in ['patent_inn', 'student_inn', 'eaeas_inn', 'rvp_inn', 'vnzh_inn', 'russia_inn']:
            doc = get_doc_by_key(key)
            assert doc is not None, f"Документ '{key}' отсутствует"
            assert doc.label == 'ИНН'


class TestParseRejectionReasons:
    def test_string_list(self):
        from utils import parse_rejection_reasons
        assert parse_rejection_reasons('["patent_inn", "photo"]') == [
            {'key': 'patent_inn', 'comment': ''},
            {'key': 'photo', 'comment': ''},
        ]

    def test_dict_list(self):
        from utils import parse_rejection_reasons
        assert parse_rejection_reasons([{'key': 'patent_inn', 'comment': 'Номер не читается'}]) == [
            {'key': 'patent_inn', 'comment': 'Номер не читается'},
        ]

    def test_invalid(self):
        from utils import parse_rejection_reasons
        assert parse_rejection_reasons('not json') == []


class TestHandleRejectedCallback:
    """Кнопка «Исправить анкету» не должна молча падать."""

    def _make_context(self, storage):
        return FSMContext(storage=storage, key=StorageKey(
            bot_id=1, chat_id=111, user_id=111, thread_id=None))

    def test_fix_rejected_sets_doc_state(self, monkeypatch, tmp_path):
        """Для документа из причин ставится его FSM-состояние, без исключений."""
        worker = {
            'id': '00001',
            'name': 'Иванов Иван Иванович',
            'citizenship': 'Патент',
            'rejection_reasons': '[{"key": "patent_inn", "comment": "Номер не читается"}]',
        }
        async def fake_get_worker(worker_id):
            return worker
        monkeypatch.setattr("handlers.commands.db.get_worker", fake_get_worker)

        storage = SQLiteStorage(":memory:")

        message = MagicMock()
        message.answer = AsyncMock()
        message.edit_text = AsyncMock()

        callback = MagicMock()
        callback.data = "fix_rejected:00001"
        callback.message = message
        callback.answer = AsyncMock()

        state = self._make_context(storage)
        _run_async(handle_rejected_callback(callback, state))

        cur = _run_async(state.get_state())
        assert cur == get_worker_form().patent_inn.state
        data = _run_async(state.get_data())
        assert data['fix_current_field'] == 'patent_inn'
        assert data['editing_rejected'] is True
        args, _ = message.answer.await_args
        assert 'ИНН' in args[0]
        _run_async(storage.close())

    def test_fix_rejected_without_reasons_falls_to_name(self, monkeypatch):
        """Пустые причины — переходим к вводу ФИО, без исключений."""
        worker = {
            'id': '00002',
            'name': 'Петров Пётр Петрович',
            'citizenship': 'Патент',
            'rejection_reasons': '[]',
        }
        async def fake_get_worker(worker_id):
            return worker
        monkeypatch.setattr("handlers.commands.db.get_worker", fake_get_worker)

        storage = SQLiteStorage(":memory:")

        message = MagicMock()
        message.answer = AsyncMock()
        message.edit_text = AsyncMock()

        callback = MagicMock()
        callback.data = "fix_rejected:00002"
        callback.message = message
        callback.answer = AsyncMock()

        state = self._make_context(storage)
        _run_async(handle_rejected_callback(callback, state))

        cur = _run_async(state.get_state())
        assert cur == get_worker_form().name.state
        _run_async(storage.close())
