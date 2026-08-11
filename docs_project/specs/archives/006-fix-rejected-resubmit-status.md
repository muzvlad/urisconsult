# Спека 006 — Исправленная анкета не возвращается в pending и не видна в UI

## Проблема

После исправления анкеты бот подтверждает сохранение, но:
1. В UI не видны исправленные данные.
2. Анкета не попадает в «колокольчик» (список pending для специалиста).

**Причина:** `bot/services/db.py`, функция `save_worker` (строка 489). Она выполняет
`INSERT ... ON CONFLICT(id) DO UPDATE SET ...` по списку `personal_keys`, в который **не входят**
`status`, `rejection_reasons`, `notified_at`. Эти служебные колонки обновляются только отдельными
функциями (`accept_worker`, `reject_worker`, `resubmit_worker`, `mark_notified`).

При подтверждении исправления `DBSaver.save_worker_data` (`bot/services/db_saver.py:41`) вычисляет
`status = 'pending'` (если `editing_rejected=True`) и передаёт его в `save_data`, но `save_worker`
этот ключ игнорирует. В итоге после исправления анкета остаётся со статусом `rejected` — не попадает
в `get_pending_workers`, специалист в UI её не видит.

## Решение

### 1. `bot/services/db_saver.py` — вернуть статус через `resubmit_worker`

В `save_worker_data` после `db.save_worker(save_data)` при `editing_rejected=True` вызвать
`await db.resubmit_worker(worker_id)` — эта функция уже делает ровно то, что нужно:
`status='pending', rejection_reasons='[]', notified_at=NULL`.

Это минимальный и безопасный фикс: не трогаем `save_worker`, не рискуем обнулить `notified_at`
обычных сохранений.

### 2. Тест

В `docs_project/tests/test_db.py` добавить тест: работник сохраняется, помечается `rejected`,
затем `DBSaver.save_worker_data` с `editing_rejected=True` и тем же `id` — статус должен стать
`pending`, `rejection_reasons` очищен, анкета видна в `get_pending_workers`.

## Критерии приёмки

1. После подтверждения исправления анкета получает статус `pending`.
2. Анкета появляется в `get_pending_workers()` (колокольчик UI).
3. Новый тест зелёный; весь прогон `pytest docs_project/tests/ UI/tests/` зелёный.

## Файлы

- `bot/services/db_saver.py` — вызов `resubmit_worker` при исправлении.
- `docs_project/tests/test_db.py` — регресс-тест.
- `docs_project/CHANGELOG.md` — запись.