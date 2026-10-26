"""Тесты новых полей модели Worker (spec 021, 022, 025, 028)."""
from src.models import Worker


def test_to_dict_contains_new_fields():
    worker = Worker(
        id='00001',
        name='Иванов Иван',
        customer='ООО Ромашка',
        legal_entity='ООО Тест',
        hr_status='employed',
        hr_status_date='01.01.2026',
        archived_at='2026-01-01T10:00:00',
    )
    data = worker.to_dict()
    assert data['customer'] == 'ООО Ромашка'
    assert data['legal_entity'] == 'ООО Тест'
    assert data['hr_status'] == 'employed'
    assert data['hr_status_date'] == '01.01.2026'
    assert data['archived_at'] == '2026-01-01T10:00:00'


def test_is_archived():
    assert Worker(id='1', name='A').is_archived is False
    assert Worker(id='1', name='A', archived_at='2026-01-01').is_archived is True
