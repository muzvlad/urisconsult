# Спека 014 — Убрать Email из бота и UI

## Проблема

Email не собирается во флоу регистрации (нет шага в цепочке, `process_email` не зарегистрирован),
но при этом он фигурирует по всему коду: в подтверждении анкеты, в клавиатуре редактирования,
в диалогах UI (отклонение, редактирование), в PDF-экспорте, в уведомлениях об отклонении.
Поле должно быть полностью убрано из пользовательского пути.

## Решение

Убрать email из всех пользовательских и служебных путей бота и UI. Колонку `email` в БД
оставляем (не разрушаем схему существующей БД, данные не трогаем) — код её больше не читает
и не пишет.

### Бот

1. `bot/handlers/registration.py` — удалить `process_email` и состояние `'email'` из
   `_build_worker_form`.
2. `bot/handlers/confirmation.py` — убрать строку email из `show_confirmation` и из `field_names`
   в `process_edit`.
3. `bot/utils.py` — убрать `('email', ...)` из `_BASE_FIELDS` и `'email'` из `_FIELD_PROMPTS`.
4. `bot/config/documents.py` — убрать `'email': 'Email'` из `FIELD_LABELS`.
5. `bot/services/db_saver.py` — убрать `email` из `save_data`.
6. `bot/services/db.py` — убрать `email` из `personal_keys` в `save_worker`.
7. `bot/fsm_types.py` — (удаляется в спеке 015, `email` там тоже убрать не надо).

### UI

8. `UI/src/services.py` — убрать `'email': 'Email'` из `field_labels` (TelegramService) и
   `('email', 'Email')` из профиля PDF-экспорта.
9. `UI/src/dialogs.py` — убрать `('email', 'Email')` из `RejectDialog.fields` и `EditDialog.fields`.
10. `UI/src/models.py`, `UI/src/api_client.py` — оставить поле `email` в модели (легаси-данные,
    обратная совместимость с API/тестами), но оно больше нигде не показывается.

## Критерии приёмки

1. Email не встречается в пользовательских текстах бота (подтверждение, уведомления, клавиатуры).
2. Email отсутствует в диалогах UI и PDF-экспорте.
3. `pytest docs_project/tests/ UI/tests/` зелёный.
