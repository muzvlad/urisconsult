# Спека 017 — Исправление логических багов

## Проблема

Несколько логических дефектов из аудита:

1. **PDF-экспорт падает KeyError** — `UI/src/services.py`: citizenship нормализуется на строке
   376, но цикл документов на строке 386 использует сырой `self.doc_service._doc_flows[citizenship]`.
   Для легаси-значений «Российская Федерация»/«РФ» — `KeyError`.
2. **Миграция v0→v1 создаёт пустые id** — `bot/services/db.py`: `meta_fields = {'id'} | ...`
   исключает `id` из `personal`, и `INSERT OR IGNORE INTO workers` вставляет строки с `id=''`.
3. **Уведомление об отклонении с пустым списком причин** — `bot/bot.py`: `if not reasons: continue`
   проверяет сырую строку `'[]'` (всегда truthy), при пустом списке уходит пустое «Необходимо
   исправить:».
4. **Malformed callback** — `bot/handlers/commands.py`: `data.split(":")[1]` без проверки формата.
5. **Мёртвая MIME-проверка** — `bot/services/file_saver.py`: `_ext_to_mime` 1:1 совпадает с
   `ALLOWED_MIME_TYPES`, условие никогда не срабатывает.
6. **«Проглатывание» любых ошибок в миграции v1→v2** — `bot/services/db.py`: `except Exception:
   pass` вокруг ALTER TABLE — ловит всё, не только «duplicate column».

## Решение

1. `UI/src/services.py` — в `export` использовать нормализованный citizenship для цикла документов.
2. `bot/services/db.py` — в `_migrate_v0_to_v1` не исключать `id` из `personal` (убрать `'id'` из
   `meta_fields`).
3. `bot/bot.py` — парсить причины до проверки и `continue` если список пуст.
4. `bot/handlers/commands.py` — в `handle_rejected_callback` проверять `':' in data` и
   `len(split) == 2`, иначе `return`.
5. `bot/services/file_saver.py` — удалить мёртвую MIME-проверку (расширение уже проверено).
6. `bot/services/db.py` — в `_migrate_v1_to_v2` ловить только `sqlite3.OperationalError`.

## Критерии приёмки

1. PDF-экспорт не падает при citizenship «Российская Федерация»/«РФ».
2. Миграция v0→v1 вставляет id из старых строк.
3. При пустых причинах отклонения уведомление не отправляется.
4. Битый callback-data не роняет обработчик.
5. `pytest docs_project/tests/ UI/tests/` зелёный.
