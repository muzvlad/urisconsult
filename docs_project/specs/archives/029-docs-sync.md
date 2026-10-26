# Спека 029 — Синхронизация документации с кодом

## Проблема

Документация описывает удалённые файлы (`UI/src/database.py`, `UI/src/splash.py`),
прямую работу UI с SQLite и старую схему БД (v2). После спек 021–028 в коде
появились заказчик, юр. лицо, встречи с уведомлениями, комментарии, HR-статус,
бейджи, фильтр по периоду и архив, но в документации их нет.

## Решение

Обновить `docs_project/README.md`, `docs_project/UI.md`, `docs_project/BOT.md`,
`UI/README.md` и добавить запись `v1.27` в `docs_project/CHANGELOG.md`.

Зафиксировать фактическое состояние:

- UI — HTTP-клиент API бота (`UI/src/api_client.py`), без прямого доступа к SQLite.
- API-сервер запускается внутри `bot/bot.py` на порту 56755 (21 маршрут).
- Схема БД v6, 4 таблицы: `workers`, `worker_documents`, `worker_meetings`, `worker_notes`.
- 147 тестов: 117 в `docs_project/tests`, 30 в `UI/tests`.
- Актуальные потоки документов: Патент 16, Студент 14, ЕАЭС 13, РВП 9, ВНЖ 10, Россия 9.
- Новые возможности UI: заказчик, юр. лицо, встречи, комментарии, HR-статус,
  бейджи, даты `ДД.ММ.ГГГГ`, фильтр по периоду, архив/возврат, замена документов.

## Файлы

- `docs_project/README.md`
- `docs_project/UI.md`
- `docs_project/BOT.md`
- `UI/README.md`
- `docs_project/CHANGELOG.md`
- `docs_project/specs/archives/029-docs-sync.md` (после завершения)

## Критерии приёмки

- В документации нет ссылок на удалённые `database.py` и `splash.py`.
- Нигде не указано, что UI читает SQLite напрямую.
- Версия схемы, количество таблиц, тестов и документов совпадает с кодом.
- Описаны запуск бота с API-сервером и настройка `API_SERVER`.
- Запись `v1.27` в CHANGELOG перечисляет спеки 021–028 и синхронизацию документации.

## Проверка

- Сверка фактов с `shared/__init__.py`, `bot/services/db.py`, `bot/api_server.py`,
  `bot/config/documents.py`, `UI/src/config.py`, `UI/src/api_client.py`.
- `python -m pytest docs_project/tests UI/tests -q` — 147 тестов.
