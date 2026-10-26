# Спека 021 — Поле «Заказчик» в боте и карточке

## Проблема

В анкете есть «Объект», но нет заказчика. Бот после объекта сразу спрашивает адрес
(`bot/handlers/registration.py:149-158`), а в карточке UI такого поля нет.

## Решение

### Схема БД v6 (общая для пакета задач)

Все новые колонки и таблицы добавляются одной миграцией, чтобы не плодить версии
при последовательной реализации спек 021–028.

`shared/__init__.py`:

- `WORKER_SCHEMA`: `customer TEXT`, `legal_entity TEXT`, `hr_status TEXT`,
  `hr_status_date TEXT`, `archived_at TEXT`.
- `WORKER_MEETINGS_SCHEMA`: `notified_at TEXT`, `reminded_at TEXT`.
- Новая `WORKER_NOTES_SCHEMA`:
  `id`, `worker_id`, `text`, `created_at`, `updated_at`, внешний ключ на `workers(id)`.

`bot/services/db.py`:

- `CURRENT_SCHEMA_VERSION = 6`.
- `_migrate_v5_to_v6()` добавляет колонки через `ALTER TABLE` с защитой от
  `sqlite3.OperationalError`, создаёт `worker_notes` и индекс `idx_wn_worker`.
- Backfill: существующим встречам выставить `notified_at` и `reminded_at` из
  `created_at`, чтобы после обновления бот не разослал уведомления по старым встречам.
- `init_db()` выполняет `WORKER_NOTES_SCHEMA`.

Для UI-only полей (`legal_entity`, `hr_status`, `archived_at`) общий
`db.save_worker()` не расширяется: иначе повторная отправка анкеты из бота затирала бы
эти значения. Они сохраняются отдельными endpoint'ами в спеках 022, 025, 028.

### Бот

- `bot/handlers/registration.py`:
  - добавить `customer` в `_build_worker_form()`;
  - новый `process_customer()` — сохраняет заказчика и спрашивает адрес объекта;
  - `process_object()` после сохранения объекта спрашивает заказчика и ставит
    состояние `customer`;
  - зарегистрировать обработчик в `register_registration_handlers()`.
- `bot/handlers/confirmation.py`: строка «Заказчик» после «Объект».
- `bot/handlers/commands.py`: `customer` в список полей, копируемых при исправлении
  отклонённой анкеты.
- `bot/utils.py`: `customer` в `_BASE_FIELDS` и `_FIELD_PROMPTS`.
- `bot/config/documents.py`: `FIELD_LABELS['customer'] = 'Заказчик'`.
- `bot/services/db_saver.py`: `customer` в `save_data`.
- `bot/services/db.py`: `customer` в `personal_keys` у `save_worker()`.

### UI

- `UI/src/models.py`: поле `customer`, `from_row()`, `to_dict()`.
- `UI/src/api_client.py`: `_dict_to_worker()`.
- `UI/src/main.py`: «Заказчик» в карточке после «Объект».
- `UI/src/dialogs.py`: `customer` в `EditDialog` и `RejectDialog`.
- `UI/src/services.py`: «Заказчик» в подписях причин отклонения и в PDF-профиле.

## Критерии приёмки

1. Бот спрашивает заказчика сразу после объекта, затем адрес объекта.
2. Заказчик сохраняется в БД и виден в карточке UI.
3. Заказчика можно отредактировать в UI и отклонить как поле анкеты.
4. Заказчик попадает в подтверждение бота и PDF.
5. Миграция v6 применяется на существующей БД без потери данных.

## Тесты

- `docs_project/tests/test_db.py`: `customer` сохраняется и читается; новые колонки
  присутствуют после `init_db()`.
- `docs_project/tests/test_handlers.py`: порядок состояний `object -> customer -> object_address`.
- `UI/tests/test_models.py`: `Worker.to_dict()` содержит `customer`.

## Риски

- Старые анкеты получат пустого заказчика — это допустимо.
- При исправлении отклонённой анкеты заказчик должен копироваться в FSM, иначе
  поле потеряется. Это покрывается тестом.
