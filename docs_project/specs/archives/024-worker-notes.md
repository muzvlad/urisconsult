# Спека 024 — Комментарии в карточке

## Проблема

Под блоком встреч нет возможности вести собственные заметки по анкете. Пользователь
UI не может добавить, изменить или удалить комментарий.

## Решение

Отдельная таблица, не смешивать комментарии с встречами.

### БД

`shared/__init__.py`, миграция v6 (спека 021):

```sql
CREATE TABLE IF NOT EXISTS worker_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);
```

Индекс `idx_wn_worker` по `worker_id`.

### API

`bot/services/db.py`:

- `get_worker_notes(worker_id) -> list[dict]`;
- `add_worker_note(worker_id, text) -> int`;
- `update_worker_note(note_id, text) -> bool`;
- `delete_worker_note(note_id) -> bool`.

`bot/api_server.py`:

- `GET /api/workers/<worker_id>/notes`;
- `POST /api/workers/<worker_id>/notes` — `{"text": "..."}`;
- `PUT /api/workers/<worker_id>/notes/<note_id>` — `{"text": "..."}`;
- `DELETE /api/workers/<worker_id>/notes/<note_id>`.

Проверка: пустой текст не сохраняется, ответ 400.

`UI/src/api_client.py`: `get_notes`, `add_note`, `update_note`, `delete_note`.

### UI

- `UI/src/main.py`: под блоком «Встречи» блок «Комментарии».
- Кнопка «+ Добавить комментарий».
- Каждый комментарий: текст с переносами, дата `дд.мм.гггг чч:мм`, кнопки
  «Изменить» и «Удалить».
- `UI/src/dialogs.py`: `NoteDialog` — многострочное `Text` height 6, «Отмена»/«Сохранить».
- Удаление — с подтверждением.
- После добавления/изменения/удаления перерисовать карточку.

## Критерии приёмки

1. Под встречами есть блок «Комментарии».
2. Комментарий добавляется, редактируется и удаляется.
3. Текст с переносами строк сохраняется без потерь.
4. После перезапуска UI комментарии на месте.
5. Пустой комментарий не сохраняется.

## Тесты

- `docs_project/tests/test_worker_notes.py`: CRUD, пустой текст, порядок по `id`.
- `docs_project/tests/test_db.py`: таблица `worker_notes` создаётся при `init_db()`.

## Риски

- При удалении анкеты комментарии удаляются каскадно только если это явно добавлено
  в `delete_worker()`. Добавить `DELETE FROM worker_notes WHERE worker_id = ?`.
