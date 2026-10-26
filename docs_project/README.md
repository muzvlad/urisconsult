# URIS Consult

Система кадрового учёта: Telegram-бот собирает анкеты сотрудников и документы,
десктопное приложение помогает обрабатывать анкеты. UI работает с данными только
через HTTP API, который запускается вместе с ботом.

## Архитектура

```
urisconsult/
├── shared/
│   └── __init__.py             # Схема БД (единый источник истины)
├── bot/                        # Telegram-бот + API-сервер
│   ├── bot.py                  # Точка входа, запуск polling и API на :56755
│   ├── api_server.py           # Flask API для UI (21 маршрут)
│   ├── utils.py                # Общие утилиты и валидаторы
│   ├── log_context.py          # Contextvars для worker_id/user_id
│   ├── middleware.py           # Rate limiting (5 сообщений / 10 секунд)
│   ├── seed_test_data.py       # Генерация тестовых анкет
│   ├── backup_db.py            # Бэкап БД
│   ├── .env                    # BOT_TOKEN, NETWORK_SERVER, API_SERVER
│   ├── config/
│   │   ├── __init__.py         # Пути, .env, ensure_dirs
│   │   └── documents.py        # Типы документов и потоки по категориям
│   ├── handlers/
│   │   ├── commands.py         # /start, /cancel, обработка отклонений
│   │   ├── registration.py     # FSM регистрации
│   │   ├── documents.py        # Загрузка/пропуск документов
│   │   └── confirmation.py     # Подтверждение и редактирование
│   ├── keyboards/
│   │   ├── reply_kb.py
│   │   └── inline_kb.py
│   ├── services/
│   │   ├── db.py               # SQLite (WAL, миграции, схема v6)
│   │   ├── db_saver.py         # Сохранение анкеты
│   │   ├── file_saver.py       # Сохранение файлов и валидация
│   │   └── fsm_storage.py      # SQLiteStorage для FSM
│   └── Users/
│       ├── users.db            # БД (локальный fallback)
│       └── docs/{worker_id}/   # Документы сотрудников
├── UI/                         # Десктопное приложение (Tkinter)
│   ├── db_viewer.py            # Точка входа (splash, retry)
│   ├── run.bat                 # Запуск с автоустановкой зависимостей
│   ├── build_exe.bat           # Сборка EXE
│   ├── build_exe.py            # PyInstaller
│   ├── requirements.txt        # Pillow, reportlab, pymupdf
│   ├── src/
│   │   ├── main.py             # GUI
│   │   ├── api_client.py       # HTTP-клиент API (stdlib urllib)
│   │   ├── models.py           # Worker и др.
│   │   ├── services.py         # Документы, Telegram, PDF
│   │   ├── widgets.py          # Список, фото, документы, колокольчик
│   │   ├── dialogs.py          # Диалоги
│   │   ├── config.py           # API_SERVER, пути, HR-статусы, даты
│   │   └── logging_config.py   # Логирование и diagnostic_log
│   └── tests/                  # 30 тестов
├── docs_project/
│   ├── README.md               # Этот файл
│   ├── BOT.md                  # Документация бота и API
│   ├── UI.md                   # Документация UI
│   ├── CHANGELOG.md            # История версий
│   ├── specs/                  # Спеки
│   └── tests/                  # 117 тестов
├── pyproject.toml
└── .gitignore
```

## Компоненты

### Telegram-бот

Бот ведёт пошаговую анкету:

1. ФИО, гражданство (6 категорий), пол
2. Дата рождения, менеджер, объект, заказчик
3. Адрес объекта, должность, телефоны
4. Для категории «Россия» — семейное положение и родственники
5. Документы по категории (9-16 штук, зависят от потока)
6. Подтверждение с возможностью редактирования полей и документов

Данные сохраняются в SQLite. Параллельно с polling бот поднимает Flask API
на `0.0.0.0:56755`, через который UI читает и изменяет анкеты.

**Запуск:**

```bash
cd bot
pip install -r requirements.txt
# Создайте .env с BOT_TOKEN=ваш_токен
python bot.py
```

Бот должен быть запущен до UI: без API-сервера UI не получит данные.

### Десктопное приложение

Tkinter-клиент для поиска, просмотра и обработки анкет.

**Возможности:**

- Поиск и фильтр по периоду (день, неделя, месяц, прошлый месяц, год, произвольный)
- Список анкет с бейджами статуса бота и HR-статуса
- Просмотр карточки, фото и документов
- Принятие и отклонение анкет с отправкой замечаний в Telegram
- Редактирование полей, юр. лица и замена документов
- Встречи с уведомлениями в Telegram
- Комментарии по сотруднику
- HR-статус с датой приёма/увольнения
- Архив и возврат из архива
- Экспорт карточки в PDF
- Колокольчик новых анкет (обновление раз в 15 секунд)

**Запуск:**

```bash
cd UI
run.bat
```

**Сборка EXE:**

```bash
cd UI
build_exe.bat
```

Результат: `UI/dist/[Search]Driver.exe`.

## Поток обработки анкеты

```
Клиент отправляет анкету
        ↓
   workers.status = pending
        ↓
   Колокольчик в UI показывает количество новых
        ↓
   Админ открывает анкету
        ↓
   ┌─ Принять → accepted
   │
   └─ Отклонить → выбор полей и комментариев
                ↓
        Бот отправляет замечания в Telegram
                ↓
        Клиент исправляет через /start
                ↓
        status = pending
```

Дополнительно ведутся `hr_status` и `archived_at`; они не меняют статус бота.

## Хранение данных

| Ресурс | Путь |
|---|---|
| БД | `bot/Users/users.db` (или `NETWORK_SERVER/bot/Users/users.db`) |
| Документы | `bot/Users/docs/{worker_id}/` (или `NETWORK_SERVER/bot/Users/docs/`) |
| Кэш документов UI | `%USERPROFILE%\.urisconsult_cache\{worker_id}\` |
| Конфиг бота | `bot/.env` |
| Логи бота | `bot/logs/bot.log` |
| Логи UI | `ui_error.log` рядом с EXE или в домашней папке |

### Таблицы БД

Определены в `shared/__init__.py` (единый источник истины):

| Таблица | Описание |
|---|---|
| `workers` | Анкета, статус бота, HR-статус, архив, юр. лицо, заказчик |
| `worker_documents` | Файлы документов; несколько файлов на один `doc_type` разрешено |
| `worker_meetings` | Встречи и отметки об уведомлениях |
| `worker_notes` | Комментарии сотрудника |

### Статусы

| Поле | Значения |
|---|---|
| `status` | `pending`, `accepted`, `rejected` |
| `hr_status` | `not_processed`, `docs_pending`, `employed`, `rejected`, `fired` |
| Архив | `archived_at` пустой или дата архивации |

## API-сервер

Запускается в `bot/bot.py` на порту `56755` (`threaded=True`). UI обращается к
нему по HTTP; прямого доступа к SQLite у UI нет.

Основные группы маршрутов:

- `GET /api/workers`, `GET /api/workers/<id>` — список и карточка
- `PUT /api/workers/<id>`, `DELETE /api/workers/<id>` — изменение и удаление
- `PUT /accept`, `/reject`, `/resubmit` — обработка анкеты
- `POST /archive`, `/unarchive` — архив
- `PUT /legal-entity`, `/hr-status` — юр. лицо и HR-статус
- `GET/POST /documents` — список и загрузка файлов
- `GET /docs/<worker_id>/<filename>` — выдача файла
- `GET /api/pending/count` — счётчик новых
- `GET/POST /meetings`, `GET/POST/PUT/DELETE /notes` — встречи и комментарии

## Версионирование схемы БД

БД использует `PRAGMA user_version`. Миграции выполняются один раз при старте.

Текущая версия: **6**.

| Версия | Изменение |
|---|---|
| 0 | Старая схема с документами в `workers` |
| 1 | Нормализованная `worker_documents` |
| 2 | Статусы и причины отклонения |
| 3 | Добавлен `updated_at` |
| 4 | Снят `UNIQUE(worker_id, doc_type)` — несколько файлов на документ |
| 5 | Заполнены пустые `created_at`/`updated_at` |
| 6 | Заказчик, юр. лицо, HR-статус, архив, встречи, комментарии |

## Тесты

Все тесты запускаются из корня проекта:

```bash
# Все тесты (147)
python -m pytest docs_project/tests UI/tests -q

# Только бот (117)
python -m pytest docs_project/tests -q

# Только UI (30)
python -m pytest UI/tests -q
```

## Конфигурация

Файл `bot/.env`:

```
BOT_TOKEN=ваш_токен_бота
NETWORK_SERVER=
API_SERVER=http://127.0.0.1:56755
```

- `BOT_TOKEN` — токен Telegram-бота
- `NETWORK_SERVER` — путь к сетевой папке; если пуст или недоступен,
  используется `bot/Users/`
- `API_SERVER` — адрес API для UI; также читается из переменной окружения.
  Приоритет: переменная окружения → `bot/.env` → `http://144.76.70.246:56755`

## Тестовые данные

```bash
cd bot
python seed_test_data.py
```

Создаёт тестовые анкеты с разными статусами и категориями.

## Требования

- Python 3.11+
- Telegram Bot Token

### Зависимости бота

- aiogram 3.x, aiohttp, aiosqlite, Flask
- python-dotenv, pydantic, Pillow, aiofiles

### Зависимости UI

- Pillow
- reportlab (PDF)
- pymupdf
