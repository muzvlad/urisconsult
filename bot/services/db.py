"""
Сервис для работы с SQLite базой данных (нормализованная схема).

Схема:
  workers            — личная информация
  worker_documents   — документы (фото, паспорта и т.д.)
  worker_meetings    — встречи
"""
import os
import json
import logging
import aiosqlite

from config import DB_PATH, USERS_DIR
from config.documents import DOC_FLOWS, DOC_PREFIXES

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


# ─── Соединение ──────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    """Получить соединение с БД (синглтон)."""
    global _db
    if _db is not None:
        try:
            await _db.execute("SELECT 1")
            return _db
        except Exception:
            try:
                await _db.close()
            except Exception:
                pass
            _db = None

    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db():
    """Закрыть соединение с БД."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ─── Инициализация ──────────────────────────────────────────────────

async def init_db():
    """Инициализация БД: создание таблиц и миграция из JSON/старой схемы."""
    db = await get_db()

    # Таблица работников (только личная информация)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workers (
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
            rejection_reasons TEXT DEFAULT '[]'
        )
    """)

    # Таблица документов (нормализовано)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS worker_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id),
            UNIQUE(worker_id, doc_type)
        )
    """)

    # Таблица встреч
    await db.execute("""
        CREATE TABLE IF NOT EXISTS worker_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            date TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)

    # Индексы
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_worker ON worker_documents(worker_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_type ON worker_documents(doc_type)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wm_worker ON worker_meetings(worker_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_workers_name ON workers(name)")

    # Миграция: добавить notified_at если нет
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN notified_at TEXT")
    except Exception:
        pass  # колонка уже существует

    await db.commit()

    # Миграция: старая схема → новая
    await _migrate_from_old_schema(db)
    # Миграция: JSON-файлы → БД
    await _migrate_from_json(db)


# ─── Миграция со старой схемы ────────────────────────────────────────

async def _migrate_from_old_schema(db: aiosqlite.Connection):
    """Если есть старая таблица workers с колонками документов — мигрировать в новую схему."""
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='workers'")
    row = await cursor.fetchone()
    if row is None:
        return

    create_sql = row[0]
    # Если в CREATE TABLE есть колонка 'patent_snils' — это старая схема
    if 'patent_snils' not in create_sql:
        return

    logger.info("Обнаружена старая схема БД. Миграция в нормализованную...")

    # Читаем все данные из старой таблицы
    cursor = await db.execute("SELECT * FROM workers")
    rows = await cursor.fetchall()
    old_columns = [desc[0] for desc in cursor.description]

    for row in rows:
        old_data = dict(zip(old_columns, row))

        # Определяем колонки документов
        doc_columns = set()
        for cat_docs in DOC_FLOWS.values():
            for doc in cat_docs:
                doc_columns.add(doc.key)

        # Личные данные — только колонки которые ЕСТЬ в старой таблице
        meta_fields = {'id'} | doc_columns | {'meetings', 'russia_marital_status', 'russia_relatives'}
        personal = {k: v for k, v in old_data.items() if k not in meta_fields}

        # Семейное положение и родственники — маппим из старых колонок если есть
        if 'russia_marital_status' in old_columns:
            personal['marital_status'] = old_data.get('russia_marital_status', '')
        if 'russia_relatives' in old_columns:
            personal['relatives_json'] = old_data.get('russia_relatives', '[]')

        # Убираем None → пустая строка
        personal = {k: (v if v is not None else '') for k, v in personal.items()}

        # Вставляем работника (без документов)
        placeholders = ', '.join(['?'] * len(personal))
        cols = ', '.join(personal.keys())
        await db.execute(f"INSERT OR IGNORE INTO workers ({cols}) VALUES ({placeholders})",
                         list(personal.values()))

        # Мигрируем документы
        for col in old_columns:
            if col in doc_columns:
                filename = old_data.get(col)
                if filename:
                    await db.execute(
                        "INSERT INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                        (old_data['id'], col, filename)
                    )

        # Мигрируем встречи
        meetings_raw = old_data.get('meetings', '[]')
        if isinstance(meetings_raw, str):
            try:
                meetings = json.loads(meetings_raw)
            except (json.JSONDecodeError, TypeError):
                meetings = []
        else:
            meetings = meetings_raw or []

        for m in meetings:
            if isinstance(m, dict):
                await db.execute(
                    "INSERT INTO worker_meetings (worker_id, date, note) VALUES (?, ?, ?)",
                    (old_data['id'], m.get('date', ''), m.get('note', m.get('description', '')))
                )

    await db.commit()

    # Переименовываем старую таблицу (бэкап)
    await db.execute("ALTER TABLE workers RENAME TO workers_old_v1")
    await db.commit()

    # Создаём новую таблицу workers
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workers (
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
            created_at TEXT
        )
    """)

    # Копируем данные из старой таблицы в новую
    await db.execute("""
        INSERT OR IGNORE INTO workers
        (id, name, citizenship, gender, position, object, object_address,
         manager, phone_main, phone_additional, email, date,
         registration, telegram_id, telegram_username, created_at)
        SELECT id, name, citizenship, gender, position, object, object_address,
               manager, phone_main, phone_additional, email, date,
               registration, telegram_id, telegram_username, created_at
        FROM workers_old_v1
    """)

    # Копируем документы из старой таблицы
    _valid_col_pattern = set()
    for docs in DOC_FLOWS.values():
        for doc in docs:
            _valid_col_pattern.add(doc.key)

    cursor = await db.execute("PRAGMA table_info(workers_old_v1)")
    old_cols = {r[1] for r in await cursor.fetchall()}

    for col in _valid_col_pattern:
        if col in old_cols and col.isidentifier():
            await db.execute(
                f"INSERT INTO worker_documents (worker_id, doc_type, filename)"
                f" SELECT id, ?, [{col}] FROM workers_old_v1 WHERE [{col}] IS NOT NULL AND [{col}] != ''",
                (col,)
            )

    # Копируем встречи
    await db.execute("""
        INSERT INTO worker_meetings (worker_id, date, note)
        SELECT id, '', meetings FROM workers_old_v1
        WHERE meetings IS NOT NULL AND meetings != '[]' AND meetings != ''
    """)

    # Удаляем старую таблицу
    await db.execute("DROP TABLE IF EXISTS workers_old_v1")
    await db.commit()
    logger.info("Миграция в нормализованную схему завершена.")


# ─── Миграция из JSON ────────────────────────────────────────────────

async def _migrate_from_json(db: aiosqlite.Connection):
    """Миграция существующих JSON-файлов в БД."""
    if not os.path.exists(USERS_DIR):
        return

    json_files = [f for f in os.listdir(USERS_DIR) if f.endswith('.json')]
    if not json_files:
        return

    # Проверяем, есть ли уже данные в БД
    cursor = await db.execute("SELECT COUNT(*) FROM workers")
    count = (await cursor.fetchone())[0]
    if count > 0:
        return  # Уже есть данные — не мигрируем

    for filename in json_files:
        filepath = os.path.join(USERS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            worker_id = data.get('id', '')
            if not worker_id:
                continue

            # Личные данные
            personal = {
                'id': worker_id,
                'name': data.get('name', ''),
                'citizenship': data.get('citizenship', ''),
                'gender': data.get('gender', ''),
                'position': data.get('position', ''),
                'object': data.get('object', ''),
                'object_address': data.get('object_address', ''),
                'manager': data.get('manager', ''),
                'phone_main': data.get('phone_main', ''),
                'phone_additional': data.get('phone_additional', ''),
                'email': data.get('email', ''),
                'date': data.get('date', ''),
                'registration': data.get('registration', ''),
                'telegram_id': data.get('telegram_id'),
                'telegram_username': data.get('telegram_username', ''),
                'created_at': data.get('created_at', ''),
            }

            placeholders = ', '.join(['?'] * len(personal))
            cols = ', '.join(personal.keys())
            await db.execute(
                f"INSERT OR IGNORE INTO workers ({cols}) VALUES ({placeholders})",
                list(personal.values())
            )

            # Документы — все ключи из DOC_FLOWS
            for cat_docs in DOC_FLOWS.values():
                for doc in cat_docs:
                    # Старый JSON мог хранить под русскими названиями
                    value = data.get(doc.key, '')
                    if not value and doc.key == 'passport':
                        value = data.get('Паспорт', '')
                    if not value and doc.key == 'patent_patent':
                        value = data.get('Патент', '')
                    if not value and doc.key == 'registration':
                        value = data.get('Регистрация', '')

                    if value:
                        await db.execute(
                            "INSERT OR IGNORE INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                            (worker_id, doc.key, value)
                        )

            # Встречи
            meetings = data.get('meetings', [])
            if isinstance(meetings, str):
                try:
                    meetings = json.loads(meetings)
                except (json.JSONDecodeError, TypeError):
                    meetings = []
            for m in (meetings or []):
                if isinstance(m, dict):
                    await db.execute(
                        "INSERT INTO worker_meetings (worker_id, date, note) VALUES (?, ?, ?)",
                        (worker_id, m.get('date', ''), m.get('note', m.get('description', '')))
                    )

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Ошибка миграции JSON %s: %s", filename, e)
            continue

    await db.commit()


# ─── CRUD операции ──────────────────────────────────────────────────

async def get_next_id() -> str:
    """Получить следующий доступный ID (атомарная операция)."""
    db = await get_db()
    async with db.execute("BEGIN IMMEDIATE"):
        cursor = await db.execute("SELECT id FROM workers ORDER BY CAST(id AS INTEGER) DESC LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            return "00001"
        try:
            next_id = int(row[0]) + 1
        except (ValueError, TypeError):
            next_id = 1
        return str(next_id).zfill(5)


async def save_worker(data: dict) -> str:
    """Сохранить работника в БД (INSERT или UPDATE по id)."""
    db = await get_db()
    worker_id = data.get('id', '')

    # Личные данные (без документов)
    personal_keys = [
        'id', 'name', 'citizenship', 'gender', 'position', 'object',
        'object_address', 'manager', 'phone_main', 'phone_additional',
        'email', 'date', 'registration', 'marital_status', 'relatives_json',
        'telegram_id', 'telegram_username', 'created_at',
    ]

    personal = {k: data.get(k, '' if k != 'telegram_id' else None) for k in personal_keys}

    placeholders = ', '.join(['?'] * len(personal))
    cols = ', '.join(personal.keys())
    await db.execute(
        f"INSERT OR REPLACE INTO workers ({cols}) VALUES ({placeholders})",
        list(personal.values())
    )

    # Документы — удаляем старые и вставляем новые
    await db.execute("DELETE FROM worker_documents WHERE worker_id = ?", (worker_id,))

    for cat_docs in DOC_FLOWS.values():
        for doc in cat_docs:
            filename = data.get(doc.key, '')
            if filename:
                await db.execute(
                    "INSERT INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                    (worker_id, doc.key, filename)
                )

    # Встречи — удаляем старые и вставляем новые
    await db.execute("DELETE FROM worker_meetings WHERE worker_id = ?", (worker_id,))

    meetings = data.get('meetings', [])
    if isinstance(meetings, str):
        try:
            meetings = json.loads(meetings)
        except (json.JSONDecodeError, TypeError):
            meetings = []
    for m in (meetings or []):
        if isinstance(m, dict):
            await db.execute(
                "INSERT INTO worker_meetings (worker_id, date, note) VALUES (?, ?, ?)",
                (worker_id, m.get('date', ''), m.get('note', m.get('description', '')))
            )

    await db.commit()
    return worker_id


async def save_documents(worker_id: str, doc_files: dict[str, str]):
    """Сохранить документы работника. doc_files = {doc_type: filename}."""
    db = await get_db()
    # Удаляем старые документы этого типа
    for doc_type in doc_files:
        await db.execute(
            "DELETE FROM worker_documents WHERE worker_id = ? AND doc_type = ?",
            (worker_id, doc_type)
        )
    # Вставляем новые
    for doc_type, filename in doc_files.items():
        if filename:
            await db.execute(
                "INSERT INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                (worker_id, doc_type, filename)
            )
    await db.commit()


async def get_worker(worker_id: str) -> dict | None:
    """Получить работника по ID (с документами и встречами)."""
    db = await get_db()

    cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = await cursor.fetchone()
    if row is None:
        return None

    result = dict(row)

    # Документы
    cursor = await db.execute(
        "SELECT doc_type, filename FROM worker_documents WHERE worker_id = ?",
        (worker_id,)
    )
    docs = await cursor.fetchall()
    result['documents'] = {row[0]: row[1] for row in docs}

    # Встречи
    cursor = await db.execute(
        "SELECT date, note FROM worker_meetings WHERE worker_id = ? ORDER BY id",
        (worker_id,)
    )
    meetings = await cursor.fetchall()
    result['meetings_list'] = [{'date': row[0], 'note': row[1]} for row in meetings]

    return result


async def get_all_workers() -> list[dict]:
    """Получить всех работников (без документов для производительности)."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM workers ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_worker_documents(worker_id: str) -> dict[str, str]:
    """Получить документы работника: {doc_type: filename}."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT doc_type, filename FROM worker_documents WHERE worker_id = ?",
        (worker_id,)
    )
    rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


async def search_workers(query: str) -> list[dict]:
    """Поиск работников по ФИО."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workers WHERE name LIKE ? ORDER BY id",
        (f"%{query}%",)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ─── Управление статусом анкеты ─────────────────────────────────────

async def get_pending_workers() -> list[dict]:
    """Получить работников со статусом pending (ожидающие обработки)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workers WHERE status = 'pending' ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_pending_count() -> int:
    """Количество анкет, ожидающих обработки."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM workers WHERE status = 'pending'"
    )
    row = await cursor.fetchone()
    return row[0]


async def accept_worker(worker_id: str):
    """Принять анкету — установить статус 'accepted'."""
    db = await get_db()
    await db.execute(
        "UPDATE workers SET status = 'accepted', rejection_reasons = '[]' WHERE id = ?",
        (worker_id,)
    )
    await db.commit()


async def reject_worker(worker_id: str, reasons: list[str]):
    """Отклонить анкету с указанием причин."""
    db = await get_db()
    await db.execute(
        "UPDATE workers SET status = 'rejected', rejection_reasons = ?, notified_at = NULL WHERE id = ?",
        (json.dumps(reasons, ensure_ascii=False), worker_id)
    )
    await db.commit()


async def resubmit_worker(worker_id: str):
    """Клиент переподал анкету — вернуть статус 'pending'."""
    db = await get_db()
    await db.execute(
        "UPDATE workers SET status = 'pending', rejection_reasons = '[]', notified_at = NULL WHERE id = ?",
        (worker_id,)
    )
    await db.commit()


async def get_worker_status(worker_id: str) -> str | None:
    """Получить статус работника."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT status FROM workers WHERE id = ?", (worker_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def mark_notified(worker_id: str):
    """Пометить работника как уведомлённого."""
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "UPDATE workers SET notified_at = ? WHERE id = ?",
        (datetime.now().isoformat(), worker_id)
    )
    await db.commit()


async def get_unnotified_rejected_workers() -> list[dict]:
    """Получить отклонённых работников, которым ещё не отправлено уведомление."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workers WHERE status = 'rejected' AND (notified_at IS NULL OR notified_at = '')"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
