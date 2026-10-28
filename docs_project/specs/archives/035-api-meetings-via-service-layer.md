# Спека 035 — Перевести работу со встречами в api_server на слой services/db

## Проблема

`bot/api_server.py:305` (маршрут `GET /api/workers/<id>/meetings`) напрямую
обращался к приватному `db._get_conn()` и сам писал SQL:

```python
async with db._get_conn() as conn:
    cursor = await conn.execute("SELECT id, date, note, created_at ...")
```

`_get_conn` приватный — это нарушало инкапсуляцию и мешало рефакторингу.

## Решение

1. `bot/services/db.py`: добавлен публичный метод

   ```python
   async def get_meetings(worker_id: str) -> list[dict]:
       """Встречи работника в порядке добавления."""
   ```

   Формат ответа совместим с прежним: `id`, `date`, `note`, `created_at`,
   сортировка по `id` — в SQL.
2. `bot/api_server.py`: маршрут вызывает `db.get_meetings(worker_id)`.
   Прямого доступа к `_get_conn` в `api_server.py` больше нет.

## Файлы

- `bot/services/db.py` — метод `get_meetings`.
- `bot/api_server.py` — маршрут `list_meetings` через сервис-слой.
- `docs_project/tests/test_api.py` — тест формы ответа `GET /meetings`.

## Критерии приёмки

- [x] `api_server.py` больше не использует `db._get_conn`.
- [x] `GET /api/workers/<worker_id>/meetings` отдаёт те же данные.
- [x] Существующие тесты `test_api.py` (встречи, заметки) проходят без правок.
- [x] Метод `get_meetings` реализован по образцу остальных методов `db`.

Серийный номер: **035**.
