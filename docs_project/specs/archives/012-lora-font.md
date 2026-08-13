# Спека 012 — Шрифт Lora во всём UI + жирные кнопки + кнопки под названием документа

## Проблема

1. Весь UI использует системный шрифт `Arial`. Нужен фирменный шрифт **Lora** везде.
2. Текст на кнопках читается плохо — нужен чуть жирнее, но чтобы не выходил за пределы кнопки.
3. В `DocumentViewer` кнопки «Скачать» и «Заменить» находятся **под фоткой** (прижаты вправо),
   а должны быть **под надписью названия документа** (слева).

## Решение

### 1. Шрифт Lora в проекте

- Скачать статические TTF-файлы Lora (Regular + Bold, с кириллицей) в `UI/assets/fonts/`.
- `UI/src/config.py`: константа `FONT_FAMILY = "Lora"` и функция `register_font(root)`:
  - на Windows — временная регистрация через `ctypes.windll.gdi32.AddFontResourceExW(..., FR_PRIVATE)`
    с fallback на `Arial`, если файл шрифта недоступен;
  - поиск пути к TTF: dev-режим — `UI/assets/fonts/Lora-Regular.ttf`, EXE — `_MEIPASS/fonts/`.
- `UI/db_viewer.py`: после создания `root` вызвать `register_font(root)`.
- `build_exe.py`: добавить `UI/assets/fonts` в бандл (`--add-data`).

### 2. Замена `Arial` → `FONT_FAMILY` во всех виджетах

Во всех `font=(...)` заменить `'Arial'` на `FONT_FAMILY` (импортируется из `src.config`):
- `UI/src/main.py`, `UI/src/widgets.py`, `UI/src/dialogs.py`, `UI/src/splash.py`.

Исключение: `('Segoe UI Symbol', ...)` в `NotificationBell` — это иконки-символы, Lora их не содержит.

### 3. Кнопки жирнее, без вылезания текста

- Всем кнопкам добавить `'bold'` вес и увеличить `padx` (≈14–16) чтобы текст не вылезал за границы.
- tkinter автоматически подстраивает размер кнопки под текст + padx — жирный текст не вылезет.

### 4. Кнопки «Скачать»/«Заменить» под названием документа

В `DocumentViewer._build_ui`:
- панель кнопок разместить **слева под названием** (кнопки `pack(side=LEFT)`), а не справа;
- миниатюра остаётся справа.

### 5. Тесты

UI-тесты не проверяют шрифты — прогон `pytest docs_project/tests/ UI/tests/` должен остаться зелёным.
Проверить импорт `src.config` без ошибок.

## Критерии приёмки

1. Весь текст в UI (заголовки, кнопки, поля) рендерится шрифтом Lora.
2. Текст на кнопках жирный и не выходит за границы кнопки.
3. В карточке документа кнопки «Скачать»/«Заменить» под названием, миниатюра справа.
4. Если Lora недоступна — UI работает на Arial (fallback).
5. `pytest docs_project/tests/ UI/tests/` зелёный; сборка exe проходит.

## Файлы

- `UI/assets/fonts/Lora-Regular.ttf`, `Lora-Bold.ttf` (новые)
- `UI/src/config.py`, `UI/src/main.py`, `UI/src/widgets.py`, `UI/src/dialogs.py`, `UI/src/splash.py`
- `UI/db_viewer.py`, `UI/build_exe.py`
- `docs_project/CHANGELOG.md`
