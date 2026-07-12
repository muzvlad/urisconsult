# URIS Consult

Комплексная система для кадрового учёта: Telegram-бот для сбора данных сотрудников + десктопное приложение для просмотра и обработки анкет.

## Архитектура

```
urisconsult/
├── bot/                        # Telegram-бот (сбор данных)
│   ├── bot.py                  # Точка входа бота
│   ├── middleware.py            # Rate limiting
│   ├── seed_test_data.py       # Генерация тестовых анкет
│   ├── backup_db.py            # Бэкап БД
│   ├── config/
│   │   ├── __init__.py         # Конфигурация (пути, ensure_dirs)
│   │   └── documents.py        # ЕДИНЫЙ конфиг документов
│   ├── handlers/
│   │   ├── commands.py         # /start, /cancel, обработка отклонений
│   │   ├── registration.py     # FSM (динамический из конфига)
│   │   ├── documents.py        # Generic handler (~160 строк)
│   │   └── confirmation.py     # Подтверждение
│   ├── keyboards/              # Клавиатуры
│   ├── services/
│   │   ├── db.py               # SQLite (нормализованная схема, reconnection)
│   │   ├── db_saver.py         # Сохранение в БД (json.dumps)
│   │   └── file_saver.py       # Сохранение файлов + валидация
│   └── logs/                   # Логи (auto-created)
├── UI/                         # Десктопное приложение
│   ├── db_viewer.py            # Точка входа UI
│   ├── src/
│   │   ├── main.py             # Tkinter GUI
│   │   ├── database.py         # Repository pattern
│   │   ├── models.py           # Worker, WorkerDocument
│   │   ├── services.py         # Document, Telegram, PDF services
│   │   ├── widgets.py          # UI компоненты
│   │   ├── dialogs.py          # Диалоги
│   │   ├── splash.py           # Splash screen
│   │   └── logging_config.py   # Логирование
│   ├── tests/                  # 86+ тестов
│   └── requirements.txt        # Зависимости
├── docs_project/
│   ├── README.md               # Этот файл
│   ├── CHANGELOG.md            # История изменений
│   ├── BOT.md                  # Документация бота
│   └── tests/                  # 62 теста (config, db, handlers)
├── users/
│   └── docs/                   # Документы сотрудников
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
pip install -r requirements.txt
python db_viewer.py
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
| БД | `bot/Users/users.db` (SQLite) |
| Документы | `users/docs/` |
| Конфиг | `bot/.env` (BOT_TOKEN) |
| Логи | `bot/logs/bot.log` |
| Бэкапы | `backups/` |

### Таблицы БД

| Таблица | Описание |
|---|---|
| `workers` | Личная информация + статус |
| `worker_documents` | Документы (worker_id, doc_type, filename) |
| `worker_meetings` | Встречи (worker_id, date, note) |

### Статусы анкет

| Статус | Описание |
|---|---|
| `pending` | Ожидает обработки (отображается в колокольчике) |
| `accepted` | Принята |
| `rejected` | Отклонена (список полей в `rejection_reasons`) |

## Тесты

```bash
cd docs_project
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

62 теста: конфиг документов, БД (CRUD, миграция), хендлеры (валидация, FSM).

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
