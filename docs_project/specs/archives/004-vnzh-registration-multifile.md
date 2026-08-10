# Спека 004 — Регистрация в ВНЖ + несколько файлов в трудовой книжке

## Проблема

1. В потоке ВНЖ (`DOC_FLOWS['ВНЖ']`) нет отдельного документа «Регистрация». Бизнес-процесс
   требует: после документа «ВНЖ» запрашивать скан/фото регистрации.
2. «Трудовая книжка / выписка из ЭТК с Госуслуг» (`vnzh_work_book`, `russia_work_book`) может
   состоять из **нескольких файлов** (сканы разворотов + выписка). Сейчас каждый документ
   принимает ровно один файл: после первого файла бот сразу переходит к следующему документу,
   а `worker_documents` имеет `UNIQUE(worker_id, doc_type)` — второй файл физически не сохранить.

## Решение

### 1. Документ «Регистрация» в потоке ВНЖ

- Новый тип: `vnzh_registration`, label «Регистрация», prefix `reg`.
- Позиция в `DOC_FLOWS['ВНЖ']`: сразу после `vnzh_vnzh`.
- Промпт: «📋 Приложите скан или фото регистрации:».
- Итого слотов ВНЖ: 9 → 10.

### 2. Несколько файлов для одного документа

- `DocumentType` получает флаг `multi_file: bool = False`.
- `vnzh_work_book` и `russia_work_book` → `multi_file=True`.
- **Бот** (`documents.py`): для `multi_file` документа после каждого файла бот НЕ переходит к
  следующему документу, а остаётся в том же FSM-состоянии и отвечает:
  «Файл получен! Пришлите ещё файл или нажмите 'Пропустить', чтобы завершить».
  Временные пути копятся в списке `{doc_key}_temp_paths`.
- **Пропуск** для `multi_file`: кнопка «Пропустить» завершает сбор этого документа —
  если файлы уже были загружены, бот сохраняет их и переходит к следующему документу;
  если файлов нет — обычный пропуск документа.
- **Сохранение**: каждый файл сохраняется в БД отдельной записью. Имя файла: первый без
  суффикса (`trud.jpg`), последующие с индексом (`trud_2.jpg`, `trud_3.jpg`, …).
  `FileSaver.save_document` получает параметр `index`.

### 3. Схема БД (миграция v3 → v4)

- Снять `UNIQUE(worker_id, doc_type)` с `worker_documents` — один документ может иметь
  несколько файлов-записей. Миграция через `PRAGMA user_version`: пересоздать таблицу без
  UNIQUE, скопировать данные, обновить версию.

### 4. Изменение контракта документов: `{doc_type: filename}` → `{doc_type: [filename, ...]}`

Затронутые места (бот и UI), возврат теперь список строк:

| Файл | Что меняется |
|---|---|
| `bot/services/db.py` | `save_documents` принимает `str \| list[str]`, `get_worker_documents` и `documents` в `get_worker` возвращают `dict[str, list[str]]` |
| `bot/services/db_saver.py` | значения `saved_files` могут быть списком |
| `bot/handlers/confirmation.py` | показ (existing docs) и сохранение multi-файлов с суффиксом |
| `bot/handlers/documents.py` | multi-file цикл приёма файлов |
| `bot/services/file_saver.py` | параметр `index` для имени файла |
| `UI/src/database.py` | `get_by_worker` → `dict[str, list[str]]` |
| `UI/src/services.py` | для multi-документа создавать `DocumentInfo` на каждый файл; PDF-экспорт |
| `UI/src/main.py` | отображение списков файлов |
| `UI/src/api_client.py` | аннотация типа `get_documents` |

`api_server.py` менять не нужно — JSON сериализует списки автоматически.

### 5. Что НЕ делаем

- Не меняем личные поля, другие категории и их порядок.
- Не добавляем multi_file другим документам.
- Не меняем `PRAGMA`-схему `workers` и `worker_meetings`.

## Проверка

1. `docs_project/tests/test_config_documents.py`: ВНЖ 9 → 10, тест позиции `vnzh_registration`
   после `vnzh_vnzh`, `multi_file` для обеих трудовых, `reg` prefix.
2. Полный прогон: `python -m pytest docs_project/tests/ UI/tests/`.
3. Вручную: регистрация ВНЖ — после ВНЖ просят регистрацию; при загрузке трудовой книжки
   можно приложить несколько файлов, «Пропустить» завершает, в карточке UI видны все файлы.
4. Пересобрать exe (`UI/build_exe.py`) — конфиг документов вшивается в бандл.

## Файлы

- `bot/config/documents.py` — тип `vnzh_registration`, флаг `multi_file`, промпт.
- `bot/services/db.py` — миграция v4, контракт списков.
- `bot/services/file_saver.py`, `bot/services/db_saver.py` — суффиксы имён, списки.
- `bot/handlers/documents.py`, `bot/handlers/confirmation.py` — цикл приёма, сохранение.
- `UI/src/{database,services,main,api_client}.py` — отображение списков файлов.
- `docs_project/tests/test_config_documents.py` — обновление счётчиков/тестов.
- `docs_project/CHANGELOG.md`, `docs_project/BOT.md` — документация.
