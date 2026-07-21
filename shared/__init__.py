"""
Общая схема базы данных для бота и UI.

Единый источник истины для структуры таблиц.
"""

# Таблицы
WORKERS_TABLE = "workers"
WORKER_DOCUMENTS_TABLE = "worker_documents"
WORKER_MEETINGS_TABLE = "worker_meetings"

# Схема таблицы работников
WORKER_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKERS_TABLE} (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    citizenship TEXT,
    gender TEXT,
    position TEXT,
    object TEXT,
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
    status TEXT DEFAULT 'pending',
    rejection_reasons TEXT DEFAULT '[]',
    notified_at TEXT
)
"""

# Схема таблицы документов
WORKER_DOCUMENTS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKER_DOCUMENTS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES {WORKERS_TABLE}(id),
    UNIQUE(worker_id, doc_type)
)
"""

# Схема таблицы встреч
WORKER_MEETINGS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {WORKER_MEETINGS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    date TEXT,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES {WORKERS_TABLE}(id)
)
"""

# Миграции: добавление колонок если их нет
MIGRATIONS = [
    ("status", "TEXT DEFAULT 'pending'"),
    ("rejection_reasons", "TEXT DEFAULT '[]'"),
    ("notified_at", "TEXT"),
]
