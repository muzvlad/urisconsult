# Спека 015 — Удаление мёртвого кода

## Проблема

В проекте есть код, который не используется в рантайме, и легаси-слой, который живёт только
для тестов. Мёртвый код усложняет навигацию и провоцирует неверные «отсылки».

## Решение

Удалить:

1. **`bot/fsm_types.py`** — `WorkerFormData` нигде не импортируется.
2. **`UI/src/splash.py`** — `SplashScreen` не используется (`UI/db_viewer.py` рисует свой splash).
   Убрать `--hidden-import=src.splash` из `UI/build_exe.py`.
3. **`UI/src/database.py`** — легаси sqlite-слой, в продакшене не используется (UI ходит через
   `APIClient`). Удалить вместе с `UI/tests/test_database.py`. После удаления:
   - `UI/src/config.py` — убрать ре-экспорт констант shared (`WORKERS_TABLE` и т.д.), если они
     больше нигде не нужны.
4. **`bot/handlers/commands.py`** — `_get_fix_keyboard`, `process_fix_choice` (и регистрацию
   `form_class.fix_choice`), т.к. состояние `fix_choice` и `rejected_worker_id` никто не ставит.
   Убрать состояние `'fix_choice'` из `_build_worker_form` в `registration.py`.
5. **`bot/services/db.py`** — `close_db()` (пустышка) и вызов в `bot/bot.py` shutdown.
6. **`UI/src/api_client.py`** — строки `w._documents`/`w._meetings` (API не возвращает такие ключи).
7. **`bot/utils.py`** — неиспользуемый ключ `'marital_status'` в `_FIELD_PROMPTS`.
8. **`bot/seed_test_data.py`** — сломан: импортирует несуществующую `db.get_db`. Переписать на
   существующий слой `db` (через `_get_conn`/`init_db`), убрать `email` из тестовых данных.

## Критерии приёмки

1. Удалённые модули не импортируются нигде в рантайме.
2. `bot/seed_test_data.py` запускается (создаёт тестовые анкеты) без ошибок.
3. `pytest docs_project/tests/ UI/tests/` зелёный.
