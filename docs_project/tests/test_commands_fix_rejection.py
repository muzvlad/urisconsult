"""
Тесты исправления анкеты по отклонённым полям (bot/handlers/commands.py).

Регресс-тест: `_ask_rejected_field` для документа не должен падать с NameError
(отсутствовал импорт get_skip_keyboard).
"""
import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from handlers.commands import _ask_rejected_field
from handlers.registration import get_worker_form
from config.documents import get_doc_by_key


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
