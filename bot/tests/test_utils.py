"""
Тесты для bot/utils.py — parse_rejection_reasons, parse_meeting_datetime,
get_field_prompt, validate_file_extension.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (  # noqa: E402
    parse_rejection_reasons,
    parse_meeting_datetime,
    get_field_prompt,
    validate_file_extension,
)


# ─── parse_rejection_reasons ──────────────────────────────────────────

def test_parse_rejection_reasons_json_string():
    """JSON-строка → список dict'ов."""
    result = parse_rejection_reasons('[{"key": "passport", "comment": "плохое фото"}]')
    assert result == [{"key": "passport", "comment": "плохое фото"}]


def test_parse_rejection_reasons_list_of_strings():
    """Список строк → [{key, comment}]."""
    result = parse_rejection_reasons(["passport", "inn"])
    assert result == [
        {"key": "passport", "comment": ""},
        {"key": "inn", "comment": ""},
    ]


def test_parse_rejection_reasons_list_of_dicts():
    """Список dict'ов →そのまま."""
    result = parse_rejection_reasons([{"key": "photo", "comment": ""}])
    assert result == [{"key": "photo", "comment": ""}]


def test_parse_rejection_reasons_bad_json():
    """Битая JSON → пустой список."""
    result = parse_rejection_reasons("not json")
    assert result == []


def test_parse_rejection_reasons_none():
    """None → пустой список."""
    result = parse_rejection_reasons(None)
    assert result == []


def test_parse_rejection_reasons_empty_list():
    """Пустой список → пустой список."""
    result = parse_rejection_reasons([])
    assert result == []


# ─── parse_meeting_datetime ───────────────────────────────────────────

def test_parse_meeting_datetime_full():
    """дд.мм.гггг чч:мм → datetime."""
    from datetime import datetime
    result = parse_meeting_datetime("01.02.2024 10:30")
    assert result == datetime(2024, 2, 1, 10, 30)


def test_parse_meeting_datetime_date_only():
    """дд.мм.гггг → datetime."""
    from datetime import datetime
    result = parse_meeting_datetime("01.02.2024")
    assert result == datetime(2024, 2, 1, 0, 0)


def test_parse_meeting_datetime_iso():
    """ISO формат → datetime."""
    from datetime import datetime
    result = parse_meeting_datetime("2024-02-01 10:30:00")
    assert result == datetime(2024, 2, 1, 10, 30)


def test_parse_meeting_datetime_invalid():
    """Неверный формат → None."""
    assert parse_meeting_datetime("abc") is None
    assert parse_meeting_datetime("") is None
    assert parse_meeting_datetime("99.99.9999") is None


# ─── get_field_prompt ─────────────────────────────────────────────────

def test_get_field_prompt_text_field():
    """Текстовое поле → prompt из _FIELD_PROMPTS."""
    assert get_field_prompt("name") == "Введите исправленное ФИО:"
    assert get_field_prompt("phone_main") == "Введите основной телефон:"


def test_get_field_prompt_document():
    """Документ → 'Отправьте исправленный файл: {label}'."""
    result = get_field_prompt("passport")
    assert result == "Отправьте исправленный файл: Паспорт"


def test_get_field_prompt_unknown_document():
    """Неизвестный документ → ключ как метка."""
    result = get_field_prompt("some_unknown_doc")
    assert result == "Отправьте исправленный файл: some_unknown_doc"


# ─── validate_file_extension ──────────────────────────────────────────

def test_validate_file_extension_ok():
    """Разрешённое расширение → True."""
    assert validate_file_extension("photo.jpg") is True
    assert validate_file_extension("doc.PDF") is True
    assert validate_file_extension("scan.Png") is True


def test_validate_file_extension_bad():
    """Неразрешённое расширение → False."""
    assert validate_file_extension("file.xyz") is False
    assert validate_file_extension("file.docx") is False
    assert validate_file_extension("file") is False
