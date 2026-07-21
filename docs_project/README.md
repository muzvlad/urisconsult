# URIS Consult

Комплексная система для кадрового учёта: Telegram-бот для сбора данных сотрудников + десктопное приложение для просмотра и обработки анкет.

## Архитектура

```
urisconsult/
├── shared/                     # Общие модули (бот + UI)
│   └── __init__.py             # Схема БД (единый источник истины)
├── bot/                        # Telegram-бот (сбор данных)
│   ├── bot.py                  # Точка входа бота
│   ├── utils.py                # Общие утилиты (get_document_state, build_edit_keyboard)
│   ├── fsm_types.py            # TypedDict для FSM данных
│   ├── log_context.py          # Contextvars для worker_id/user_id в логах
│   ├── middleware.py            # Rate limiting (с фоновой очисткой)
│   ├── seed_test_data.py       # Генерация тестовых анкет
│   ├── backup_db.py            # Бэкап БД
│   ├── .env                    # Конфигурация (BOT_TOKEN, NETWORK_SERVER)
│   ├── config/
│   │   ├── __init__.py         # Конфигурация (пути, .env, ensure_dirs)
│   │   └── documents.py        # ЕДИНЫЙ конфиг документов (frozen dataclass)
│   ├── handlers/
│   │   ├── commands.py         # /start, /cancel, обработка отклонений
│   │   ├── registration.py     # FSM (ленивая инициализация WorkerForm)
│   │   ├── documents.py        # Generic handler (~160 строк)
│   │   └── confirmation.py     # Подтверждение + edit_keyboard из конфига
│   ├── keyboards/
│   │   ├── reply_kb.py         # Reply клавиатуры
│   │   └── inline_kb.py        # Inline клавиатуры
│   ├── services/
│   │   ├── db.py               # SQLite (WAL, BEGIN IMMEDIATE, версионирование)
│   │   ├── db_saver.py         # Сохранение в БД
│   │   └── file_saver.py       # Сохранение файлов + валидация
│   └── Users/
│       ├── users.db            # База данных
│       └── docs/               # Документы сотрудников
│           ├── 00001/
│           ├── 00002/
│           └── 00003/
├── UI/                         # Десктопное приложение
│   ├── db_viewer.py            # Точка входа (splash → main)
│   ├── run.bat                 # Запуск (с автоустановкой зависимостей)
│   ├── build_exe.bat           # Сборка EXE
│   ├── build_exe.py            # Скрипт сборки
│   ├── src/
│   │   ├── main.py             # Tkinter GUI
│   │   ├── database.py         # Repository pattern (WAL, retry, 15s timeout)
│   │   ├── models.py           # Worker, WorkerDocument
│   │   ├── services.py         # Document, Telegram, PDF services
│   │   ├── widgets.py          # UI компоненты
│   │   ├── dialogs.py          # Диалоги
│   │   ├── config.py           # Конфигурация (пути, сетевой сервер из .env)
│   │   ├── splash.py           # Splash screen
│   │   └── logging_config.py   # Логирование + diagnostic_log
│   ├── tests/                  # 46 тестов
│   └── requirements.txt        # Зависимости
├── docs_project/
│   ├── README.md               # Этот файл
│   ├── BOT.md                  # Документация бота
│   ├── UI.md                   # Документация UI
│   ├── CHANGELOG.md            # История версий
│   └── tests/                  # 62 теста (config, db, handlers)
├── pyproject.toml              # Конфигурация проекта
└── .gitignore
```

## Компоненты

### Telegram-бот

Бот ведёт пошаговую анкету сотрудника через Telegram:

1. ФИО, гражданство (6 категорий), пол
2. Должность, объект, адрес, менеджер
3. Телефон, email, дата рождения
4. Загрузка документов (7-12 в зависимости от категории)
5. Экран подтверждения с возможностью редактирования

Данные сохраняются в SQLite (`bot/Users/users.db`).

**Запуск:**
```bash
cd bot
pip install -r requirements.txt
# Создайте .env с BOT_TOKEN=ваш_токен
python bot.py
```

### Десктопное приложение

GUI для просмотра и обработки анкет сотрудников.

**Возможности:**
- Поиск по ФИО
- Просмотр всех записей со статусом (⏳/✅/❌)
- **Колокольчик уведомлений** — новые анкеты
- **Обработка анкет** — принятие / отклонение с выбором полей
- **Отправка замечаний** клиенту в Telegram
- Документы по категории гражданства
- Экспорт в PDF

**Запуск:**
```bash
cd UI
# Автоматически создаст venv и установит зависимости
run.bat
```

**Сборка EXE:**
```bash
cd UI
build_exe.bat
```

## Система обработки анкет

```
Клиент отправляет анкету
        ↓
   Статус: pending
        ↓
   Колокольчик в UI показывает уведомление
        ↓
   Админ открывает список анкет
        ↓
   ┌─ Принять → статус accepted (колокольчик убирает)
   │
   └─ Отклонить → выбор полей → сообщение клиенту в Telegram
                ↓
        Клиент исправляет → /start → исправление полей
                ↓
        Статус: pending (снова в колокольчике)
```

## Хранение данных

| Ресурс | Путь |
|---|---|
| БД | `bot/Users/users.db` (SQLite, WAL mode) |
| Документы | `bot/Users/docs/` |
| Конфиг | `bot/.env` (BOT_TOKEN, NETWORK_SERVER) |
| Логи | `bot/logs/bot.log` |

### Таблицы БД

Определены в `shared/__init__.py` (единый источник истины для бота и UI):

| Таблица | Описание |
|---|---|
| `workers` | Личная информация + статус |
| `worker_documents` | Документы (worker_id, doc_type, filename) UNIQUE |
| `worker_meetings` | Встречи (worker_id, date, note) |

### Статусы анкет

| Статус | Описание |
|---|---|
| `pending` | Ожидает обработки (отображается в колокольчике) |
| `accepted` | Принята |
| `rejected` | Отклонена (список полей в `rejection_reasons`) |

## Версионирование схемы БД

БД использует `PRAGMA user_version` для отслеживания версии схемы. Миграции выполняются **один раз** при обновлении версии.

Текущая версия: **2** (normalize schema + status fields).

## Тесты

Все тесты запускаются из корня проекта:

```bash
# Все тесты (108 штук)
python -m pytest UI/tests/ docs_project/tests/ -v

# Только UI тесты (46)
python -m pytest UI/tests/ -v

# Только тесты бота (62)
python -m pytest docs_project/tests/ -v
```

## Конфигурация

### Файл `.env`

```
BOT_TOKEN=ваш_токен_бота
NETWORK_SERVER=\\144.76.70.246\urisconsult
```

- `BOT_TOKEN` — токен Telegram бота (от @BotFather)
- `NETWORK_SERVER` — адрес сетевого сервера (если пустой — используется локальная БД)

### `pyproject.toml`

Стандартная конфигурация Python проекта с зависимостями и настройками pytest.

## Тестовые данные

```bash
cd bot
python seed_test_data.py
```

Создаёт 5 анкет (Тестовый*) с разными статусами и категориями.

## Требования

- Python 3.11+
- Telegram Bot Token (от @BotFather)

### Зависимости бота
- aiogram 3.x
- aiosqlite
- python-dotenv

### Зависимости UI
- Pillow
- reportlab (для PDF)

### Зависимости тестов
- pytest
- pytest-asyncio
