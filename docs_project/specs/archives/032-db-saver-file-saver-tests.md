# Спека 032 — Тесты для bot/services/db_saver.py + file_saver.py

## Проблема

`DBSaver.save_worker_data` и `FileSaver.save_document` — ключевая цепочка сохранения анкеты и файлов. **Покрыто на 0%.**

## Решение

### DBSaver тесты (`bot/tests/test_db_saver.py`)

| Функция | Что проверяет |
|---------|--------------|
| `save_worker_data` | Новый работник: создаёт ID, сохраняет личные данные, документы, статус pending |
| `save_worker_data` | editing_rejected=True → статус pending после сохранения |
| `save_worker_data` | telegram_username сохраняется если передан |
| `get_next_id` | Делегирует в `db.get_next_id` |

### FileSaver тесты (`bot/tests/test_file_saver.py`)

| Функция | Что проверяет |
|---------|--------------|
| `validate_file` | Слишком большой файл → False + сообщение |
| `validate_file` | Недопустимое расширение → False + сообщение |
| `validate_file` | Корректный файл → True + пустая строка |
| `save_document` | Сохраняет файл с правильным именем (prefix + ext) |
| `save_document` | multi_file (index > 1) → prefix_{index}.ext |
| `save_document` | Временный файл не найден → FileNotFoundError |
| `save_document` | Невалидный файл → ValueError |
| `cleanup_temp_files` | Удаляет существующие временные файлы, не падает на отсутствующие |

### Фикстуры

- `temp_db` — временный файл БД (как в тесте 031)
- `temp_dir` — временная папка для DOCS_DIR и файлов

### Файлы

- `bot/tests/test_db_saver.py`
- `bot/tests/test_file_saver.py`
- Спека 032 заархивировать в `docs_project/specs/archives/`

Серийный номер: **032**.
