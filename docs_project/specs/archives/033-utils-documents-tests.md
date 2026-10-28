# Спека 033 — Тесты для bot/utils.py + config/documents.py

## Проблема

`utils.py` (parse_rejection_reasons, parse_meeting_datetime, build_edit_keyboard, get_field_prompt) и `config/documents.py` (DOC_FLOWS, get_next_doc, get_doc_by_key, DOC_PREFIXES) — бизнес-логика без БД. **Покрыто на 0%.**

## Решение

### utils.py тесты (`bot/tests/test_utils.py`)

| Функция | Что проверяет |
|---------|--------------|
| `parse_rejection_reasons` | JSON-строка → список dict'ов |
| `parse_rejection_reasons` | Список строк → [{key, comment}] |
| `parse_rejection_reasons` | Список dict'ов →そのまま |
| `parse_rejection_reasons` | Битая JSON → пустой список |
| `parse_meeting_datetime` | Форматы дд.мм.гггг чч:мм, дд.мм.гггг, ISO → datetime |
| `parse_meeting_datetime` | Неверный формат → None |
| `get_field_prompt` | Текстовое поле → prompt из _FIELD_PROMPTS |
| `get_field_prompt` | Документ → "Отправьте исправленный файл: {label}" |
| `validate_file_extension` | Разрешённое расширение → True |
| `validate_file_extension` | Неразрешённое → False |

### documents.py тесты (`bot/tests/test_documents_config.py`)

| Функция | Что проверяет |
|---------|--------------|
| `DOC_FLOWS` | Каждая категория имеет документы, ключи уникальны |
| `get_next_doc` | Возвращает следующий документ в цепочке |
| `get_next_doc` | Последний документ → None |
| `get_doc_by_key` | Находит документ по ключу из любой категории |
| `DOC_PREFIXES` | Каждый ключ документа имеет префикс |
| `DOC_LABELS` | Каждый ключ имеет метку |
| `get_doc_flow` | Неизвестная категория → PATENT (fallback) |

### Файлы

- `bot/tests/test_utils.py`
- `bot/tests/test_documents_config.py`
- Спека 033 заархивировать в `docs_project/specs/archives/`

Серийный номер: **033**.
