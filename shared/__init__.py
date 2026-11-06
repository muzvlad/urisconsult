"""
Общая схема базы данных для бота и UI.

Единый источник истины для структуры таблиц и для времени записи.
"""
from datetime import datetime, timedelta, timezone

# Москва = UTC+3 круглый год (переход на летнее время отменён с 2014).
MSK = timezone(timedelta(hours=3))


def now_msk() -> datetime:
    """Текущее время по Москве, naive (без смещения в строке).

    Смещение (+03:00) намеренно не записывается: SQLite разбирает такую
    строку как UTC и переводит её назад, из-за чего date(created_at)
    уезжал бы на сутки. Всё, что пишется в БД как время, идёт отсюда.
    """
    return datetime.now(MSK).replace(tzinfo=None)


# Таблицы
WORKERS_TABLE = "workers"
WORKER_DOCUMENTS_TABLE = "worker_documents"
WORKER_MEETINGS_TABLE = "worker_meetings"
WORKER_NOTES_TABLE = "worker_notes"

# Схема таблицы работников
WORKER_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKERS_TABLE} (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    citizenship TEXT,
    gender TEXT,
    position TEXT,
    object TEXT,
    customer TEXT,
    object_address TEXT,
    manager TEXT,
    phone_main TEXT,
    phone_additional TEXT,
    email TEXT,
    date TEXT,
    registration TEXT,
    marital_status TEXT,
    relatives_json TEXT DEFAULT '[]',
    telegram_id INTEGER,
    telegram_username TEXT,
    created_at TEXT,
    updated_at TEXT,
    status TEXT DEFAULT 'pending',
    rejection_reasons TEXT DEFAULT '[]',
    notified_at TEXT,
    legal_entity TEXT,
    hr_status TEXT DEFAULT 'not_processed',
    hr_status_date TEXT,
    documents_signed TEXT DEFAULT '0',
    archived_at TEXT
)
"""

# Схема таблицы документов
# UNIQUE(worker_id, doc_type) снят: multi-file документы хранят несколько файлов одного типа
WORKER_DOCUMENTS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKER_DOCUMENTS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', '+3 hours')),
    FOREIGN KEY (worker_id) REFERENCES {WORKERS_TABLE}(id)
)
"""

# Схема таблицы встреч
WORKER_MEETINGS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKER_MEETINGS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    date TEXT,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now', '+3 hours')),
    notified_at TEXT,
    reminded_at TEXT,
    FOREIGN KEY (worker_id) REFERENCES {WORKERS_TABLE}(id)
)
"""

# Схема таблицы комментариев
WORKER_NOTES_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKER_NOTES_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (worker_id) REFERENCES {WORKERS_TABLE}(id)
)
"""

# Миграции: добавление колонок если их нет
MIGRATIONS = [
    ("status", "TEXT DEFAULT 'pending'"),
    ("rejection_reasons", "TEXT DEFAULT '[]'"),
    ("notified_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("customer", "TEXT"),
    ("legal_entity", "TEXT"),
    ("hr_status", "TEXT DEFAULT 'not_processed'"),
    ("hr_status_date", "TEXT"),
    ("documents_signed", "TEXT DEFAULT '0'"),
    ("archived_at", "TEXT"),
]
