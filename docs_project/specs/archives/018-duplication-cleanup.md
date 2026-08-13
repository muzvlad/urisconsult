# Спека 018 — Дублирование и мелкие чистки

## Проблема

1. `citizenship_map {'Российская Федерация': 'Россия', 'РФ': 'Россия'}` продублирован 4 раза:
   `UI/src/services.py` (get_worker_documents, export, _count_pdf_items), `UI/src/main.py`,
   `UI/src/dialogs.py`.
2. `UI/src/main.py` парсит `relatives_json` вручную, хотя у `Worker` есть готовый `relatives`.
3. `setup.bat` использует `!VAR!` (отложенное расширение) без `setlocal enabledelayedexpansion` —
   токен и `API_SRV` не подставляются.
4. Корневая папка `users/` — неиспользуемый легаси (код работает с `bot/Users`).

## Решение

1. Добавить `normalize_citizenship(c: str) -> str` в `UI/src/config.py` и заменить все 4 карты на
   вызов. Для UI Citizenship в `services.py` и `main.py`/`dialogs.py`.
2. `UI/src/main.py` — использовать `worker.relatives` вместо ручного `json.loads`.
3. `setup.bat` — добавить `setlocal enabledelayedexpansion` в начало.
4. Удалить корневую `users/` (не трекается в git, легаси-данные).

## Критерии приёмки

1. В коде нет дублирующихся `citizenship_map`.
2. `setup.bat` корректно раскрывает `!GITHUB_TOKEN!`/`!API_SRV!`.
3. `pytest docs_project/tests/ UI/tests/` зелёный.
