# URIS Consult

Комплексная система для кадрового учёта: Telegram-бот для сбора данных сотрудников + десктопное приложение для просмотра карточек.

## Архитектура

```
urisconsult/
├── bot/                        # Telegram-бот (сбор данных)
│   ├── bot.py                  # Точка входа бота
│   ├── config.py               # Конфигурация (пути, префиксы документов)
│   ├── handlers/               # Обработчики сообщений
│   │   ├── commands.py         # /start, /cancel
│   │   ├── registration.py     # FSM: пошаговый ввод данных
│   │   ├── documents.py        # Загрузка документов (6 категорий)
│   │   └── confirmation.py     # Подтверждение и сохранение в БД
│   ├── keyboards/              # Клавиатуры
│   ├── services/               # Сервисы
│   │   ├── db.py               # SQLite (aiosqlite)
│   │   ├── db_saver.py         # Сохранение в БД
│   │   └── file_saver.py       # Сохранение документов
│   └── Users/
│       └── users.db            # Общая база данных
├── UI/                         # Десктопное приложение (просмотр)
│   ├── db_viewer.py            # Tkinter GUI — чтение из SQLite
│   ├── build_exe.py            # Сборка в .exe
│   ├── requirements.txt        # Зависимости (Pillow, reportlab)
│   └── run.bat                 # Скрипт запуска
├── users/
│   └── docs/                   # Общая папка документов
│       ├── photo_00001.jpg     # Фото сотрудника
│       ├── pas_00001.jpg       # Паспорт
│       ├── pat_00001.jpg       # Патент
│       └── ...
└── docs/                       # Документация проекта
    ├── README.md               # Этот файл
    ├── BOT.md                  # Документация бота
    └── UI.md                   # Документация UI
```

## Компоненты

### Telegram-бот (`bot/`)

Бот ведёт пошаговую анкету сотрудника через Telegram:

1. ФИО, гражданство (6 категорий), пол
2. Должность, объект, адрес, менеджер
3. Телефон, email, дата рождения
4. Загрузка документов (от 7 до 12 в зависимости от категории)
5. Экран подтверждения с возможностью редактирования

Данные сохраняются в SQLite (`bot/Users/users.db`), документы — в `users/docs/`.

**Запуск:**
```bash
cd bot
pip install -r requirements.txt
# Создайте .env с BOT_TOKEN=ваш_токен
python bot.py
```

### Десктопное приложение (`UI/`)

GUI для просмотра карточек сотрудников. Читает ту же SQLite БД и ту же папку документов.

**Возможности:**
- Поиск по ФИО
- Просмотр всех записей
- Документы по категории гражданства
- Просмотр фото и документов (открытие в стандартном приложении)
- Экспорт в PDF

**Запуск:**
```bash
cd UI
pip install -r requirements.txt
python db_viewer.py
```

**Сборка .exe:**
```bash
python build_exe.py
# Результат: dist/[Search]Driver.exe
```

## Хранение данных

| Что | Где |
|---|---|
| База данных | `bot/Users/users.db` (SQLite) |
| Документы | `users/docs/` |
| Конфиг бота | `bot/.env` (BOT_TOKEN) |

### Именование документов

Шаблон: `{prefix}_{ID}.{расширение}`

| Префикс | Тип документа |
|---|---|
| `photo` | Фото |
| `pas` | Паспорт |
| `pat` | Патент |
| `reg` | Регистрация |
| `snils` | СНИЛС |
| `inn` | ИНН |
| `mig` | Миграционная карта |
| `dms` | ДМС |
| `bank` | Реквизиты банковской карты |
| `dactyl` | Дактилоскопическая карта |
| `trud` | Трудовая книжка/ЭТК |
| `propiska` | Прописка |
| `vnzh` | ВНЖ |
| `voen` | Военный билет |
| `edu` | Документ об образовании |
| `lang` | Сертификат о знании языка |
| `chek` | Чек по патенту |
| `spravka` | Справка из ВУЗа |

## Категории гражданства

| Категория | Кол-во документов |
|---|---|
| Патент | 12 |
| Студент | 10 |
| ЕАЭС | 9 |
| ВНЖ | 9 |
| Россия | 9 |
| РВП | 7 |

Подробное описание каждого документа — в `docs/BOT.md` и `docs/UI.md`.

## Требования

- Python 3.7+
- Telegram Bot Token (от @BotFather)

### Зависимости бота
- aiogram 3.0
- aiosqlite
- Pillow
- python-dotenv

### Зависимости UI
- Pillow
- reportlab (для PDF)

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/muzvlad/urisconsult.git
cd urisconsult

# Бот
cd bot
pip install -r requirements.txt
echo BOT_TOKEN=ваш_токен > .env
cd ..

# UI
cd UI
pip install -r requirements.txt
cd ..
```

## Запуск

```bash
# Бот
cd bot && python bot.py

# UI
cd UI && python db_viewer.py
```

Или через скрипты:
- `bot/start_bot.bat` — запуск бота
- `UI/run.bat` — запуск UI
