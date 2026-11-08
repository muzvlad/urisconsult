# URIS Consult — десктопное приложение

Tkinter-клиент для просмотра и обработки анкет сотрудников. Данные получает по
HTTP от API-сервера, который запускается вместе с Telegram-ботом. SQLite
напрямую не открывает.

Полная документация: `docs_project/UI.md`.

## Запуск

```bash
cd UI
run.bat
```

`run.bat` создаёт `.venv`, устанавливает зависимости и запускает `db_viewer.py`.
Перед этим запустите бота: API слушает `:56755`.

Вручную:

```bash
pip install -r requirements.txt
python db_viewer.py
```

## Сборка EXE

```bash
build_exe.bat
```

Результат: `dist/[Search]Driver.exe`.

## Возможности

- Поиск и фильтр по периоду
- Активные, архив и все анкеты
- Бейджи статуса бота и HR-статуса
- Принятие и отклонение с замечаниями
- Редактирование полей и юр. лица
- Замена и открытие документов
- Встречи и уведомления в Telegram
- Комментарии
- HR-статус с датой
- Архив и возврат
- Экспорт в PDF
- Колокольчик новых анкет

## Структура

```
UI/
├── db_viewer.py          # Точка входа (splash, retry)
├── build_exe.py          # PyInstaller
├── build_exe.bat
├── run.bat
├── requirements.txt      # Pillow, reportlab, pymupdf
├── src/
│   ├── main.py           # GUI
│   ├── api_client.py     # HTTP-клиент
│   ├── models.py
│   ├── services.py       # Документы, Telegram, PDF
│   ├── widgets.py
│   ├── dialogs.py
│   ├── config.py         # API_SERVER, HR-статусы, даты
│   └── logging_config.py
├── tests/                # 36 тестов
└── assets/fonts/         # Lora
```

## Настройка API

Приоритет адреса API:

1. Переменная окружения `API_SERVER`
2. `API_SERVER=` в `bot/.env` или `.env` в корне
3. `http://144.76.70.246:56755`

Документы кэшируются в `%USERPROFILE%\.urisconsult_cache\{worker_id}\`.
Таймаут запроса — 30 секунд.

## Тесты

```bash
python -m pytest UI/tests -q
```

36 тестов.

## Требования

- Python 3.11+
- Windows
- Запущенный API-сервер бота
- Pillow, reportlab, pymupdf
