# Спецификация 057 — убрать NameError и падение на нетекстовых сообщениях

## Проблема
- `bot/handlers/documents.py:40` использует `ALLOWED_EXTENSIONS` без импорта → `NameError` вместо понятного сообщения о неверном формате.
- Текстовые состояния (`name`, `gender`, `date`, `manager`, …) зарегистрированы без фильтра `F.text`: фото или документ в таком состоянии даёт `AttributeError: 'NoneType' object has no attribute 'strip'` и роняет обработчик.
- Состояние `edit` (`confirmation.py`) — та же проблема: `message.text.strip()` без проверки.
- `UI/src/main.py:728` — `Path` без импорта, вне `try`; `UI/src/services.py:302` — `ImageReader` импортируется внутри `export()`, но используется в `_draw_worker_card` → фото молча пропадает из PDF-карточки.
- `PUT /api/workers/<id>/hr-status`: пустая дата приходит как `''` → `400 Invalid hr_status_date`, то есть очистить дату HR-статуса из UI невозможно.

## Что изменить
- Импортировать `ALLOWED_EXTENSIONS` в `documents.py`.
- Текстовые хендлеры регистрируются с фильтром `F.text`; для всех текстовых состояний добавляется один общий ответ «Отправьте текстом».
- `process_edit_value` регистрируется с `F.text` + общий ответ для нетекстовых сообщений в состоянии `edit`.
- Добавить `from pathlib import Path` в `UI/src/main.py`; `ImageReader` импортировать внутри `_draw_worker_card`.
- API: пустая дата HR-статуса нормализуется в `None`; для `employed`/`fired` дата обязательна (спека 047) и проверяется на уровне API.

## Критерий приемки
Неверный формат файла даёт понятный текст, а не `NameError`; фото в текстовом состоянии даёт «Отправьте текстом» без исключения; очистка даты HR-статуса сохраняется; `employed` без даты отклоняется с 400.

## ponytail
Только `F.text` и `StateFilter` из aiogram; ни одной новой зависимости.
