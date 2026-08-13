# Спека 013 — Multi-file документы: потеря всех файлов кроме последнего

## Проблема

Для multi-file документов (трудовая книжка, военный билет) бот загружает несколько файлов в один
temp-путь, из-за чего все файлы кроме последнего теряются, а при сохранении последний файл
копируется под все имена (`trud.jpg`, `trud_2.jpg`, ...).

`bot/handlers/documents.py` в `_download_document`:

```python
temp_path = os.path.join(DOCS_DIR, f"temp_{doc_key}_{message.from_user.id}{ext}")
await bot.download_file(file_path, temp_path)
```

Имя temp-файла детерминировано (по `doc_key` и `user_id`). При загрузке второго файла того же
multi-file документа предыдущий файл на диске перезаписывается, а в `{doc_key}_temp_paths`
складываются одинаковые пути. Подтверждено репро-скриптом: 2 загрузки → 2 одинаковых пути и одно
содержимое на диске.

## Решение

Добавить порядковый номер в имя temp-файла для multi-file документов. Счётчик — длина уже
накопленного списка `{doc_key}_temp_paths` + 1.

```python
paths = data.get(f'{doc_key}_temp_paths', [])
# в multi-ветке:
temp_path = os.path.join(DOCS_DIR, f"temp_{doc_key}_{len(paths)+1}_{message.from_user.id}{ext}")
```

Для обычных документов имя не меняем (перезаливка файла перезаписывает temp — ожидаемо).

Дополнительно: в multi-ветке `temp_files.extend(paths)` дублирует пути при каждой загрузке
(накопленный список копируется в `temp_files` целиком каждый раз). Складывать в `temp_files`
только новый `temp_path`.

## Файлы

- `bot/handlers/documents.py` — уникальное имя temp-файла для multi-file + фикс дублей в `temp_files`.

## Критерии приёмки

1. Два файла одного multi-file документа сохраняются с разным содержимым под `trud.jpg`/`trud_2.jpg`.
2. Обычные документы сохраняются как раньше.
3. `pytest docs_project/tests/ UI/tests/` зелёный.
