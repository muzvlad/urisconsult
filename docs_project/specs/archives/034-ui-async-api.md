# Спека 034 — UI: убрать зависания GUI при сетевых запросах к API

## Проблема

Все запросы к API в `UI/src/api_client.py` синхронные с `timeout=30`. Главный поток Tkinter блокируется на время каждого запроса:
- `_auto_refresh_bell` каждые 15 сек делает `get_pending_count()` — висит GUI.
- `_execute_search` при поиске — висит GUI.

Если сервер отвечает медленно или таймаутит — окно показывает "Не отвечает".

## Решение

1. `UI/src/main.py`:
   - `_auto_refresh_bell` — API-запрос выполняется в daemon-потоке `threading`, обновление UI через `root.after(0, ...)`.
   - `_execute_search` — API-запрос выполняется в daemon-потоке `threading`, обновление UI через `root.after(0, ...)`.
   - Добавлен `import threading`.
2. Таймауты в `api_client.py` оставлены без изменений (30/60 сек).

## Файлы

- `UI/src/main.py` — `_auto_refresh_bell` и `_execute_search` в фоновых потоках.
- `docs_project/CHANGELOG.md` — запись v1.30.
- `docs_project/specs/archives/034-ui-async-api.md` — эта спека (после завершения).

## Критерии приёмки

- GUI не замирает на время сетевых запросов.
- Колокольчик обновляется в фоне каждые 15 сек без блокировки окна.
- Поиск не вешает GUI на 30 секунд.
- `python -m py_compile UI/src/main.py` — OK.
- 222 теста всё ещё проходят.

Серийный номер: **034**.
