# Спека 031 — Тесты для bot/services/db.py

## Проблема

`bot/services/db.py` (980 строк) — ядро системы: init_db, миграции v0→v6, CRUD работников, документов, встреч, комментариев, управление статусами. **Покрыто тестами на 0%.**

## Решение

Создать `bot/tests/test_db_service.py` с 25 тестами на async SQLite (aiosqlite) с использованием временного файла БД.

### Тестируемые функции

| Функция | Что проверяет |
|---------|--------------|
| `get_next_id` | Первый ID 00001, инкремент, уникальность |
| `save_worker` | INSERT, UPDATE (ON CONFLICT), created_at не перезаписывается |
| `get_worker` | Возвращает работника с документами, None если не найден |
| `save_documents` | Один файл, multi-file список |
| `replace_document` | Удаляет старую запись |
| `get_all_workers` | Исключает `__reserved__` |
| `search_workers` | LIKE по имени |
| `accept/reject/resubmit` | Переключение статусов |
| `get_pending_count` | Считает pending без сирот и архива |
| `set_legal_entity` | Сохраняет юр. лицо |
| `set_hr_status` | Сохраняет статус, требует дату для employed/fired |
| `archive/unarchive` | Мягкое удаление/возврат |
| `delete_worker` | Каскадное удаление (документы, встречи, заметки) |
| `add_meeting` / `get_unnotified_meetings` / `get_meetings_to_remind` | CRUD встреч |
| `mark_meeting_notified` / `mark_meeting_reminded` | Пометка о времени |
| `add_worker_note` / `update_worker_note` / `delete_worker_note` | CRUD комментариев, пустой текст не сохраняется |
| `init_db` | PRAGMA user_version = 6, все 4 таблицы |

### Фикстуры

- `temp_db` — временный файл БД в `tmp_path`, подмена `db.DB_PATH` и `db.USERS_DIR`, вызов `init_db()`

### Файлы

- `bot/tests/test_db_service.py` — новые тесты
- `docs_project/specs/archives/031-db-tests.md` — эта спека (после завершения)

## Критерии приёмки

- Все тесты проходят: `python -m pytest bot/tests -q`
- Покрытие `bot/services/db.py` существенно выросло
- Нет зависимостей от сетевой папки, БД создается во временной директории

Серийный номер: **031**.
