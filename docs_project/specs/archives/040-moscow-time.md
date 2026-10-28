# Спека 040 — Время в БД и в логике бота: всегда московское

## Проблема

Время в системе бралось из трёх разных источников, и ни один не был московским:

1. `datetime.now()` — локальное время **машины**. На сервере выставлен
   `Montevideo Standard Time` (UTC−3): расхождение с Москвой — **6 часов**,
   а не 3.
2. `DEFAULT CURRENT_TIMESTAMP` в SQLite — всегда **UTC**.
3. `datetime('now')` в SQL — тоже **UTC**.

Последствия:

- «Залит: ДД.ММ.ГГГГ ЧЧ:ММ» в UI показывалось на 3 часа раньше реальной
  загрузки (UTC против Москвы).
- Логика напоминания о встречах (`bot.py: check_meeting_notifications`)
  сравнивает дату встречи, введённую сотрудником **по московскому времени**, с
  `datetime.now()` — на машине с не-московским TZ отправка уведомления и
  напоминания «за 24 часа» сдвигалась на 6 часов.

## Решение

1. `shared/__init__.py` — единый источник времени:

   ```python
   MSK = timezone(timedelta(hours=3))  # Москва = UTC+3 круглый год

   def now_msk() -> datetime:
       """Текущее время по Москве, naive (без смещения в строке)."""
       return datetime.now(MSK).replace(tzinfo=None)
   ```

   Смещение `+03:00` в строку **не пишется**: SQLite разбирает такую строку
   как UTC и переводит её назад, из-за чего `date(created_at)` уезжал бы на
   сутки и ломался бы фильтр по периоду. Храним московское «стенное» время
   без маркера часового пояса.
2. Все места, которые пишут время, переведены на `now_msk()`:
   - `bot/services/db.py` — `save_worker`, `save_documents`, `replace_document`,
     `get_next_id` (резерв ID), `mark_notified`, `set_legal_entity`,
     `set_hr_status`, `archive_worker`, `unarchive_worker`, `add_meeting`,
     `add_worker_note`, `update_worker_note`, `cutoff` для чистки резервов;
   - `bot/api_server.py` — `updated_at` при обновлении анкеты;
   - `bot/services/db_saver.py` — `created_at`/`updated_at`;
   - `bot/bot.py` — `now` в фоновой задаче уведомлений о встречах;
   - `bot/seed_test_data.py`, `bot/backup_db.py` — время в данных и в имени
     файла бэкапа.
3. `add_meeting` и `save_worker` (вставка встреч) теперь пишут `created_at`
   явно — раньше они полагались на `DEFAULT CURRENT_TIMESTAMP` (UTC).
4. `shared/__init__.py` — `DEFAULT (datetime('now', '+3 hours'))` в схеме
   `worker_documents` и `worker_meetings` (для новых БД).
5. `bot/services/db.py` — миграция v5→v6 и таблица v3→v4: `datetime('now')` →
   `datetime('now', '+3 hours')`.

Смещение `+03:00` фиксированное: переход на летнее время в РФ отменён
с октября 2014 года, DST больше нет.

## Файлы

- `shared/__init__.py` — `MSK`, `now_msk()`, дефолты схемы.
- `bot/services/db.py`, `bot/api_server.py`, `bot/services/db_saver.py`,
  `bot/bot.py`, `bot/seed_test_data.py`, `bot/backup_db.py` — переход на
  `now_msk()`.
- `bot/tests/test_db_service.py` — тесты московского времени.

## Критерии приёмки

- [x] Всё, что пишется в БД как время, — московское, независимо от TZ машины.
- [x] `datetime.now()` в боте не осталось.
- [x] `DEFAULT CURRENT_TIMESTAMP` и `datetime('now')` без `+3 hours` не осталось.
- [x] `date(created_at)` в SQLite возвращает правильную дату (смещение не
      переводится назад).
- [x] Логика напоминания о встречах считает «за 24 часа» по московскому времени.
- [x] UI показывает московские даты в формате `ДД.ММ.ГГГГ ЧЧ:ММ`.
- [x] 227 тестов проходят.

Серийный номер: **040**.
