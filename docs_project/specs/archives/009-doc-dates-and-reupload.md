# Спека 009 — Даты анкеты и документов + перезаливка документов из UI

## Проблемы

1. **Не у всех анкет отображаются даты.** У старых/мигрированных из JSON анкет колонки
   `workers.created_at` / `workers.updated_at` пустые — UI показывает даты только если они непустые.
2. **Нет даты заливки документа.** `worker_documents.created_at` существует в схеме, но API
   (`GET /api/workers/<id>/documents`) возвращает только `{doc_type: [filename, ...]}` — дата не
   доходит до UI.
3. **Нет перезаливки документа из UI.** В API нет эндпоинта загрузки файла, в UI нет кнопки.

## Требования

1. Во всех анкетах отображаются обе даты: «Дата заведения» и «Последнее редактирование».
2. Из UI можно перезалить (заменить) документ в анкете.
3. Под названием каждого документа показывается дата его заливки; при перезаливке дата
   обновляется и сохраняется в БД.

## Решение

### 1. Гарантировать даты у всех анкет (БД)

**Миграция v4 → v5** (`bot/services/db.py`):
- `UPDATE workers SET created_at = updated_at WHERE created_at IS NULL OR created_at = ''`
- `UPDATE workers SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''`
  (после первого шага created_at уже непустой)
- `CURRENT_SCHEMA_VERSION = 5`

**`save_worker`**: при INSERT если `created_at` пуст — ставить `datetime.now()`; при UPDATE всегда
`updated_at = datetime.now()`, если `updated_at` не передали явно.

### 2. Даты заливки документов в API

`db.get_worker_documents` → возвращать подробный формат:

```python
{doc_type: [{"filename": "...", "created_at": "..."}, ...]}
```

`GET /api/workers/<id>/documents` отдаёт этот формат. (UI пересобирается, обратная совместимость
со старым exe не нужна — его всё равно пересобираем.)

### 3. Перезаливка документа из UI

**Бот, API** (`bot/api_server.py`):
- `POST /api/workers/<worker_id>/documents` — multipart-форма: `doc_type`, `file`, опционально
  `old_filename`.
- Логика:
  - файл из `request.files['file']` временно сохраняется (например, в temp),
  - если `old_filename` указан: удалить старый файл с диска и запись
    `(worker_id, doc_type, old_filename)` из `worker_documents`, новый файл сохранить под **тем же
    именем** (перезапись) → `created_at` обновится.
  - если `old_filename` пуст: сохранить новый файл через `FileSaver.save_document` и добавить запись.
- После перезаливки обновить `workers.updated_at = now` (анкета редактировалась).

**Бот, db**: добавить `replace_document(worker_id, doc_type, old_filename)` — удаляет файл и запись,
возвращает имя файла для переиспользования.

### 4. UI

**`DocumentInfo`** (`UI/src/services.py`): добавить поле `uploaded_at: str = ""`.

**`UI/src/api_client.py`**:
- `get_documents` → возвращает `{doc_type: [{filename, created_at}, ...]}`.
- новый `replace_document(worker_id, doc_type, old_filename, file_path) -> bool` — multipart POST.

**`UI/src/widgets.py`** (`DocumentViewer`):
- под названием документа строка «Залит: {дата}» (формат `ДД.ММ.ГГГГ ЧЧ:ММ`), если дата есть.
- кнопка «📤 Заменить» → `filedialog.askopenfilename` → вызывает `replace_document` → после успеха
  перерисовывает карточку анкеты.

**`UI/src/main.py`** (даты анкеты):
- всегда показывать обе даты; если поле пусто — показывать «—».

### 5. Тесты

- `docs_project/tests/test_db.py`: миграция v4→v5 (backfill дат); `replace_document` удаляет старую
  запись и вставляет новую.
- `docs_project/tests/test_config_documents.py` — не меняется.
- UI-тесты: `DocumentInfo.uploaded_at`, разбор `get_documents` нового формата.

## Критерии приёмки

1. Все анкеты в UI показывают «Дата заведения» и «Последнее редактирование».
2. Под каждым документом видна дата заливки.
3. Кнопка «Заменить» в карточке документа открывает выбор файла, заменяет документ, дата
   заливки обновляется в UI и в БД.
4. `pytest docs_project/tests/ UI/tests/` зелёный.

## Файлы

- `bot/services/db.py` — миграция v5, backfill, `replace_document`, detailed-контракт.
- `bot/api_server.py` — эндпоинт `POST .../documents`.
- `UI/src/api_client.py`, `UI/src/services.py`, `UI/src/widgets.py`, `UI/src/main.py`.
- `docs_project/tests/test_db.py`, `UI/tests/*`.
- `docs_project/CHANGELOG.md`.
