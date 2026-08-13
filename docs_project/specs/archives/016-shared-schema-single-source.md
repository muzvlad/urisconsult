# Спека 016 — Единый источник истины схемы + зависимости pyproject

## Проблема

1. `shared/__init__.py` объявляет `UNIQUE(worker_id, doc_type)` в `worker_documents`, но реальная
   схема бота этот UNIQUE сняла (миграция v4, multi-file документы). Два определения схемы
   расходятся.
2. Бот не использует `shared` — схема продублирована в `bot/services/db.py`. При изменении
   колонок надо править два места.
3. `pyproject.toml` не содержит `flask` (нужен API-серверу бота) и `pymupdf` (нужен UI для
   миниатюр PDF). `pip install -e .` не поставит их.

## Решение

### 1. `shared/__init__.py`

Снять `UNIQUE(worker_id, doc_type)` из `WORKER_DOCUMENTS_SCHEMA` — привести к реальной схеме.

### 2. Бот использует `shared`

- `bot/config/__init__.py` — добавить корень проекта в `sys.path` (чтобы `import shared` работал
  при запуске из `bot/`).
- `bot/services/db.py` — в `init_db` импортировать `WORKER_SCHEMA`, `WORKER_DOCUMENTS_SCHEMA`,
  `WORKER_MEETINGS_SCHEMA` из `shared` и использовать их вместо инлайн-`CREATE TABLE`.
  Индексы и логику очистки/миграций оставить.

### 3. `pyproject.toml` и `requirements.txt`

- Добавить `flask>=3.0.0` и `pymupdf>=1.24.0` в `pyproject.toml` dependencies.
- Добавить `pymupdf>=1.24.0` в корневой `requirements.txt` (фласк там уже есть).

## Критерии приёмки

1. `WORKER_DOCUMENTS_SCHEMA` без UNIQUE.
2. `init_db` бота создаёт идентичную схему (проверяется тестами `test_db.py`).
3. `python bot/bot.py` импортируется без `ModuleNotFoundError: shared`.
4. `pytest docs_project/tests/ UI/tests/` зелёный.
