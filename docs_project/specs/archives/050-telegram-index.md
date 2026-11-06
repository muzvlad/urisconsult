# Спецификация 007 — индекс на workers(telegram_id)

## Проблема
`bot/handlers/commands.py:136` `_find_rejected_worker` ищет по `telegram_id`, но индекса нет. При росте базы поиск отклонённой анкеты пользователя — линейный скан.

## Что изменить
Добавить `CREATE INDEX IF NOT EXISTS idx_workers_telegram ON workers(telegram_id)` в `init_db` рядом с остальными индексами (`bot/services/db.py:126-130`).

## Критерий приемки
После `init_db` в схеме есть индекс `idx_workers_telegram`; поиск по `telegram_id` использует индекс (EXPLAIN QUERY PLAN).

## ponytail
Одна строка CREATE INDEX.
