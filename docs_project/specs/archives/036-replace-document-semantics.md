# Спека 036 — Привести в порядок семантику замены документа

## Проблема

`replace_document` в `bot/services/db.py` делал только `DELETE` из
`worker_documents`. `bot/api_server.py` при наличии `old_filename` копировал
новый файл под тем же именем (перезаписывал), после чего вызывал удаление
записи. В итоге файл лежал на диске, а записи в БД не было — имя метода не
соответствовало поведению.

В `worker_documents` есть только `created_at` (нет `updated_at`), поэтому при
замене содержимого логично обновлять именно `created_at` — так фиксируется
дата реальной замены.

## Решение

1. `bot/services/db.py`:
   - `replace_document` теперь выполняет
     `UPDATE worker_documents SET created_at = ? WHERE worker_id = ? AND doc_type = ? AND filename = ?`
     и возвращает `bool` (была ли запись);
   - docstring приведён в соответствие с поведением.
2. `bot/api_server.py`:
   - файл перезаписывается под тем же именем (`shutil.copy2` перезаписывает
     существующий файл, отдельное удаление не требуется);
   - вызывается `db.replace_document`, который обновляет `created_at` записи.
3. Тесты переписаны под корректную семантику:
   - `docs_project/tests/test_db.py::test_replace_document`;
   - `bot/tests/test_db_service.py::test_replace_document`;
   - `docs_project/tests/test_api.py::TestDocumentsApi` — проверка всей связки
     UI → API → бот: файл перезаписан под тем же именем, запись в БД осталась,
     `created_at` обновился.

## Побочная правка

`save_documents` теперь пишет `created_at` явно локальным временем. Раньше
значение бралось из `DEFAULT CURRENT_TIMESTAMP`, а это **UTC** — из-за чего
«Залит: ДД.ММ.ГГГГ ЧЧ:ММ» в UI показывалось на 3 часа раньше, чем загружено.

## Файлы

- `bot/services/db.py` — `replace_document`, `save_documents`.
- `bot/api_server.py` — ветка перезаливки.
- `docs_project/tests/test_db.py`, `bot/tests/test_db_service.py`,
  `docs_project/tests/test_api.py` — тесты.

## Критерии приёмки

- [x] При замене файла запись в `worker_documents` остаётся (тот же `doc_type`, тот же `filename`).
- [x] `created_at` обновляется при замене.
- [x] Файл физически перезаписывается под тем же именем.
- [x] Тесты `test_replace_document` обновлены и проходят.
- [x] `docs_project/tests/test_api.py` проходит.
- [x] Связка UI → API → бот работает (покрыта тестом API).

Серийный номер: **036**.
