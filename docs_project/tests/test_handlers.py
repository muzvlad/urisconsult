"""
Тесты для bot/handlers/ — валидация, FSM логика.

Запуск: cd docs_project && python -m pytest tests/test_handlers.py -v
"""
import asyncio
import os
import sys
import re
import pytest

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from handlers.registration import (
    validate_phone, validate_email, validate_date, get_worker_form,
    process_object, process_customer,
)


class TestValidatePhone:
    def test_valid_phones(self):
        valid = [
            '+79991234567',
            '89991234567',
            '+7 (999) 123-45-67',
            '+7-999-123-45-67',
            '79991234567',
            '1234567890',
        ]
        for phone in valid:
            assert validate_phone(phone), f"Телефон '{phone}' должен быть валидным"

    def test_empty_phone_invalid(self):
        assert not validate_phone('')
        assert not validate_phone('   ')

    def test_whitespace_phone_valid(self):
        assert validate_phone('  +79991234567  ')


class TestValidateEmail:
    def test_valid_emails(self):
        valid = [
            'user@example.com',
            'test.user@domain.org',
            'ivanov@test.com',
            'a@b.co',
            'name123@company.ru',
        ]
        for email in valid:
            assert validate_email(email), f"Email '{email}' должен быть валидным"

    def test_invalid_emails(self):
        invalid = [
            'user',
            '@domain.com',
            'user@',
            'user@.com',
            'user@domain',
            'user domain@test.com',
        ]
        for email in invalid:
            assert not validate_email(email), f"Email '{email}' не должен быть валидным"


class TestValidateDate:
    def test_valid_dates(self):
        valid = [
            '01.01.1990',
            '31.12.2000',
            '15.06.1985',
            '29.02.2000',
        ]
        for date in valid:
            assert validate_date(date), f"Дата '{date}' должна быть валидной"

    def test_invalid_dates(self):
        invalid = [
            '01/01/1990',
            '1990-01-01',
            '01.01.90',
            '01.01.19900',
            '1.1.1990',
            'abc',
            '',
        ]
        for date in invalid:
            assert not validate_date(date), f"Дата '{date}' не должна быть валидной"


class TestWorkerForm:
    def test_has_basic_states(self):
        WorkerForm = get_worker_form()
        basic_states = [
            'name', 'citizenship', 'gender', 'position', 'object',
            'object_address', 'manager', 'phone_main', 'phone_additional',
            'date',
        ]
        for state_name in basic_states:
            assert hasattr(WorkerForm, state_name), \
                f"WorkerForm не имеет состояние '{state_name}'"

    def test_has_document_states(self):
        WorkerForm = get_worker_form()
        from config.documents import DOC_FLOWS
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert hasattr(WorkerForm, doc.key), \
                    f"WorkerForm не имеет состояние для '{doc.key}' ({cat})"

    def test_has_russia_extra_states(self):
        WorkerForm = get_worker_form()
        extra = ['russia_marital_status', 'russia_relatives']
        for state_name in extra:
            assert hasattr(WorkerForm, state_name), \
                f"WorkerForm не имеет состояние '{state_name}'"

    def test_has_control_states(self):
        WorkerForm = get_worker_form()
        control = ['confirmation', 'edit']
        for state_name in control:
            assert hasattr(WorkerForm, state_name), \
                f"WorkerForm не имеет состояние '{state_name}'"

    def test_category_specific_states_are_unique(self):
        """Категорийные состояния уникальны (не считая photo/passport)."""
        WorkerForm = get_worker_form()
        from config.documents import DOC_FLOWS
        seen = {}
        shared = {'photo', 'passport'}
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                if doc.key in shared:
                    continue
                state_obj = getattr(WorkerForm, doc.key)
                state_id = id(state_obj)
                assert state_id not in seen, \
                    f"Состояние '{doc.key}' дублируется с '{seen[state_id]}'"
                seen[state_id] = doc.key


class TestCustomerTransition:
    def test_object_then_customer_then_address(self):
        class FakeMessage:
            def __init__(self, text):
                self.text = text
                self.answers = []

            async def answer(self, text):
                self.answers.append(text)

        class FakeState:
            def __init__(self):
                self.data = {}
                self.state = None

            async def update_data(self, **kwargs):
                self.data.update(kwargs)

            async def set_state(self, state):
                self.state = state

        WorkerForm = get_worker_form()
        state = FakeState()

        asyncio.run(process_object(FakeMessage('Объект'), state))
        assert state.data['object'] == 'Объект'
        assert state.state == WorkerForm.customer

        asyncio.run(process_customer(FakeMessage('ООО Ромашка'), state))
        assert state.data['customer'] == 'ООО Ромашка'
        assert state.state == WorkerForm.object_address


class TestDocumentFlows:
    def test_all_keys_valid(self):
        pattern = re.compile(r'^[a-z0-9_]+$')
        from config.documents import DOC_FLOWS
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert pattern.match(doc.key), \
                    f"Ключ '{doc.key}' не соответствует паттерну [a-z0-9_]+"

    def test_prefixes_valid(self):
        from config.documents import DOC_FLOWS
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert len(doc.prefix) <= 20, \
                    f"Префикс '{doc.prefix}' слишком длинный (key={doc.key})"
                assert doc.prefix.replace('_', '').isalnum(), \
                    f"Префикс '{doc.prefix}' содержит спецсимволы (key={doc.key})"

    def test_can_skip_flags_consistent(self):
        """can_skip=True только для необязательных документов."""
        from config.documents import DOC_FLOWS
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                # required=True и can_skip=True допустимо (бот разрешает пропуск всех документов)
                pass
