"""
Слой работы с SQLite базой данных (нормализованная схема).

Каждая операция открывает своё соединение и сразу закрывает —
БД не блокируется между вызовами, UI работает параллельно.

Схема:
  workers            — личная информация
  worker_documents   — документы (фото, паспорта и т.д.)
  worker_meetings    — встречи

Версионирование: миграции выполняются ОДИН раз через PRAGMA user_version.
"""
import os
import json
import logging
import aiosqlite
from contextlib import asynccontextmanager

from config import DB_PATH, USERS_DIR
from config.documents import DOC_FLOWS, DOC_PREFIXES

logger = logging.getLogger(__name__)

# ─── Текущая версия схемы ──────────────────────────────────────────
CURRENT_SCHEMA_VERSION = 5


# ─── Соединение ──────────────────────────────────────────────────────

@asynccontextmanager
async def _get_conn():
    """Контекстный менеджер: открывает соединение, отдаёт, закрывает."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        await conn.close()


async def close_db():
    """Ничего не делает — соединения больше не глобальные."""
    pass


# ─── Инициализация ──────────────────────────────────────────────────

async def init_db():
    """Инициализация БД: создание таблиц и миграция по версиям."""
    async with _get_conn() as db:
        # Таблица работников
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
                updated_at TEXT,
                status TEXT DEFAULT 'pending',
                rejection_reasons TEXT DEFAULT '[]',
                notified_at TEXT
            )
        """)

        # Таблица документов
        # multi_file документы (трудовая книжка) хранят НЕСКОЛЬКО записей с одним doc_type
        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (worker_id) REFERENCES workers(id)
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

        await db.commit()

        # Очистка записей-сирот: __reserved__ от прерванных регистраций
        await db.execute("DELETE FROM workers WHERE name = '__reserved__'")
        await db.commit()

        # Версионированные миграции
        cursor = await db.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current_version = row[0]

        if current_version < CURRENT_SCHEMA_VERSION:
            logger.info("Миграция БД: версия %d → %d", current_version, CURRENT_SCHEMA_VERSION)
            await _run_migrations(db, current_version)
            await db.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            await db.commit()
            logger.info("Миграция БД завершена. Текущая версия: %d", CURRENT_SCHEMA_VERSION)


async def _run_migrations(db: aiosqlite.Connection, from_version: int):
    """Запустить миграции от from_version до CURRENT_SCHEMA_VERSION."""
    if from_version < 1:
        await _migrate_v0_to_v1(db)
    if from_version < 2:
        await _migrate_v1_to_v2(db)
    if from_version < 3:
        await _migrate_v2_to_v3(db)
    if from_version < 4:
        await _migrate_v3_to_v4(db)
    if from_version < 5:
        await _migrate_v4_to_v5(db)


# ─── Миграция v0 → v1: старая схема с колонками документов ──────────

async def _migrate_v0_to_v1(db: aiosqlite.Connection):
    """Если есть старая таблица workers с колонками документов — мигрировать."""
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='workers'")
    row = await cursor.fetchone()
    if row is None:
        return

    create_sql = row[0]
    if 'patent_snils' not in create_sql:
        return

    logger.info("Миграция v0→v1: старая схема с колонками документов")

    cursor = await db.execute("SELECT * FROM workers")
    rows = await cursor.fetchall()
    old_columns = [desc[0] for desc in cursor.description]

    for row in rows:
        old_data = dict(zip(old_columns, row))

        doc_columns = set()
        for cat_docs in DOC_FLOWS.values():
            for doc in cat_docs:
                doc_columns.add(doc.key)

        meta_fields = {'id'} | doc_columns | {'meetings', 'russia_marital_status', 'russia_relatives'}
        personal = {k: v for k, v in old_data.items() if k not in meta_fields}

        if 'russia_marital_status' in old_columns:
            personal['marital_status'] = old_data.get('russia_marital_status', '')
        if 'russia_relatives' in old_columns:
            personal['relatives_json'] = old_data.get('russia_relatives', '[]')

        personal = {k: (v if v is not None else '') for k, v in personal.items()}

        placeholders = ', '.join(['?'] * len(personal))
        cols = ', '.join(personal.keys())
        await db.execute(f"INSERT OR IGNORE INTO workers ({cols}) VALUES ({placeholders})",
                         list(personal.values()))

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

    await db.execute("ALTER TABLE workers RENAME TO workers_old_v1")

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

    await db.execute("""
        INSERT INTO worker_meetings (worker_id, date, note)
        SELECT id, '', meetings FROM workers_old_v1
        WHERE meetings IS NOT NULL AND meetings != '[]' AND meetings != ''
    """)

    await db.execute("DROP TABLE IF EXISTS workers_old_v1")
    logger.info("Миграция v0→v1 завершена.")


# ─── Миграция v1 → v2: добавление колонок + JSON миграция + sync ────

async def _migrate_v1_to_v2(db: aiosqlite.Connection):
    """Миграция v1→v2: добавление notified_at, миграция JSON, синхронизация файлов."""
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN notified_at TEXT")
    except Exception:
        pass

    try:
        await db.execute("ALTER TABLE workers ADD COLUMN status TEXT DEFAULT 'pending'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN rejection_reasons TEXT DEFAULT '[]'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN updated_at TEXT")
    except Exception:
        pass

    await _migrate_from_json(db)
    await _sync_docs_from_disk(db)

    logger.info("Миграция v1→v2 завершена.")


# ─── Миграция v2 → v3: добавление updated_at ─────────────────────

async def _migrate_v2_to_v3(db: aiosqlite.Connection):
    """Миграция v2→v3: добавление колонки updated_at."""
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN updated_at TEXT")
        logger.info("Миграция v2→v3: добавлена колонка updated_at")
    except Exception:
        pass
    await db.commit()


# ─── Миграция v3 → v4: снять UNIQUE(worker_id, doc_type) ─────────────

async def _migrate_v3_to_v4(db: aiosqlite.Connection):
    """Миграция v3→v4: worker_documents без UNIQUE — документ может иметь несколько файлов."""
    await db.execute("""
        CREATE TABLE worker_documents_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)
    await db.execute("""
        INSERT INTO worker_documents_v4 (id, worker_id, doc_type, filename, created_at)
        SELECT id, worker_id, doc_type, filename, created_at FROM worker_documents
    """)
    await db.execute("DROP TABLE worker_documents")
    await db.execute("ALTER TABLE worker_documents_v4 RENAME TO worker_documents")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_worker ON worker_documents(worker_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_type ON worker_documents(doc_type)")
    await db.commit()
    logger.info("Миграция v3→v4: снят UNIQUE(worker_id, doc_type) в worker_documents")

# ─── Миграция v4 → v5: backfill дат created_at/updated_at ─────────────

async def _migrate_v4_to_v5(db: aiosqlite.Connection):
    """Миграция v4→v5: заполнить пустые created_at/updated_at у старых анкет."""
    await db.execute("""
        UPDATE workers SET created_at = updated_at
        WHERE created_at IS NULL OR created_at = ''
    """)
    await db.execute("""
        UPDATE workers SET updated_at = created_at
        WHERE updated_at IS NULL OR updated_at = ''
    """)
    await db.commit()
    logger.info("Миграция v4→v5: backfill дат created_at/updated_at завершён")

async def _migrate_from_json(db: aiosqlite.Connection):
    """Миграция существующих JSON-файлов в БД."""
    if not os.path.exists(USERS_DIR):
        return

    json_files = [f for f in os.listdir(USERS_DIR) if f.endswith('.json')]
    if not json_files:
        return

    cursor = await db.execute("SELECT COUNT(*) FROM workers")
    count = (await cursor.fetchone())[0]
    if count > 0:
        return

    for filename in json_files:
        filepath = os.path.join(USERS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            worker_id = data.get('id', '')
            if not worker_id:
                continue

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

            for cat_docs in DOC_FLOWS.values():
                for doc in cat_docs:
                    value = data.get(doc.key, '')
                    if not value and doc.key == 'passport':
                        value = data.get('Паспорт', '')
                    if not value and doc.key == 'patent_patent_front':
                        value = data.get('Патент', '')
                    if value:
                        await db.execute(
                            "INSERT OR IGNORE INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                            (worker_id, doc.key, value)
                        )

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


# ─── Синхронизация файлов на диске → БД ──────────────────────────────

async def _sync_docs_from_disk(db: aiosqlite.Connection):
    """Сканировать users/docs/ и дописать недостающие записи в worker_documents."""
    from config import DOCS_DIR

    if not os.path.isdir(DOCS_DIR):
        return

    cursor = await db.execute("SELECT id FROM workers")
    worker_ids = {row[0] for row in await cursor.fetchall()}

    prefix_to_doc = {}
    for cat_docs in DOC_FLOWS.values():
        for doc in cat_docs:
            prefix_to_doc[doc.prefix] = doc.key

    added = 0
    for worker_id in worker_ids:
        worker_dir = os.path.join(DOCS_DIR, worker_id)
        if not os.path.isdir(worker_dir):
            continue

        cursor = await db.execute(
            "SELECT doc_type FROM worker_documents WHERE worker_id = ?", (worker_id,)
        )
        existing = {row[0] for row in await cursor.fetchall()}

        for filename in os.listdir(worker_dir):
            if filename.startswith('.') or filename.startswith('temp_'):
                continue
            prefix = os.path.splitext(filename)[0]
            doc_type = prefix_to_doc.get(prefix)
            if doc_type and doc_type not in existing:
                await db.execute(
                    "INSERT OR IGNORE INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                    (worker_id, doc_type, filename)
                )
                added += 1

        # Коммит после каждого работника чтобы не держать блокировку долго
        if added:
            await db.commit()
        logger.info("Синхронизировано %d документов из файловой системы", added)


# ─── CRUD операции ──────────────────────────────────────────────────

async def get_next_id() -> str:
    """Получить следующий доступный ID (без race condition)."""
    async with _get_conn() as db:
        for _ in range(100):  # ponytail: limit以防无限循环
            cursor = await db.execute("SELECT id FROM workers ORDER BY CAST(id AS INTEGER) DESC LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                next_id = 1
            else:
                try:
                    next_id = int(row[0]) + 1
                except (ValueError, TypeError):
                    next_id = 1
            next_id_str = str(next_id).zfill(5)
            try:
                await db.execute(
                    "INSERT INTO workers (id, name, created_at) VALUES (?, '__reserved__', '')",
                    (next_id_str,)
                )
                await db.commit()
                logger.debug("get_next_id: created __reserved__ id=%s", next_id_str)
                return next_id_str
            except Exception:
                # ponytail: IntegrityError — ID занят, пробуем следующий
                continue
        raise RuntimeError("Не удалось сгенерировать уникальный ID после 100 попыток")


async def save_worker(data: dict) -> str:
    """Сохранить работника в БД (INSERT или UPDATE по id)."""
    from datetime import datetime
    async with _get_conn() as db:
        worker_id = data.get('id', '')

        # Гарантируем даты: created_at только при INSERT, updated_at при каждом сохранении
        now = datetime.now().isoformat()
        created_at = data.get('created_at') or now
        updated_at = data.get('updated_at') or now

        personal_keys = [
            'id', 'name', 'citizenship', 'gender', 'position', 'object',
            'object_address', 'manager', 'phone_main', 'phone_additional',
            'email', 'date', 'registration', 'marital_status', 'relatives_json',
            'telegram_id', 'telegram_username',
        ]

        personal = {k: data.get(k, '' if k != 'telegram_id' else None) for k in personal_keys}
        personal['created_at'] = created_at
        personal['updated_at'] = updated_at

        placeholders = ', '.join(['?'] * len(personal))
        cols = ', '.join(personal.keys())
        update_cols = [k for k in personal.keys() if k not in ('id', 'created_at')]
        update_clause = ', '.join(f"{k} = excluded.{k}" for k in update_cols)
        await db.execute(
            f"INSERT INTO workers ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {update_clause}",
            list(personal.values())
        )

        if 'meetings' in data:
            await db.execute("DELETE FROM worker_meetings WHERE worker_id = ?", (worker_id,))

            meetings = data.get('meetings')
            if isinstance(meetings, str):
                try:
                    meetings = json.loads(meetings)
                except (json.JSONDecodeError, TypeError):
                    meetings = []
            if meetings:
                for m in (meetings or []):
                    if isinstance(m, dict):
                        await db.execute(
                            "INSERT INTO worker_meetings (worker_id, date, note) VALUES (?, ?, ?)",
                            (worker_id, m.get('date', ''), m.get('note', m.get('description', '')))
                        )

        await db.commit()
        return worker_id


async def save_documents(worker_id: str, doc_files: dict[str, str | list[str]]):
    """Сохранить документы работника. doc_files = {doc_type: filename | [filename, ...]}."""
    async with _get_conn() as db:
        for doc_type in doc_files:
            await db.execute(
                "DELETE FROM worker_documents WHERE worker_id = ? AND doc_type = ?",
                (worker_id, doc_type)
            )
        for doc_type, value in doc_files.items():
            filenames = value if isinstance(value, list) else [value]
            for filename in filenames:
                if filename:
                    await db.execute(
                        "INSERT INTO worker_documents (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                        (worker_id, doc_type, filename)
                    )
        await db.commit()


async def replace_document(worker_id: str, doc_type: str, old_filename: str):
    """Удалить старую запись документа (перезаливка из UI). created_at обновится при вставке."""
    async with _get_conn() as db:
        await db.execute(
            "DELETE FROM worker_documents WHERE worker_id = ? AND doc_type = ? AND filename = ?",
            (worker_id, doc_type, old_filename)
        )
        await db.commit()


async def get_worker(worker_id: str) -> dict | None:
    """Получить работника по ID (с документами и встречами)."""
    async with _get_conn() as db:
        cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        row = await cursor.fetchone()
        if row is None:
            return None

        result = dict(row)

        cursor = await db.execute(
            "SELECT doc_type, filename, created_at FROM worker_documents WHERE worker_id = ? ORDER BY id",
            (worker_id,)
        )
        docs = await cursor.fetchall()
        doc_map: dict[str, list[dict]] = {}
        for row in docs:
            doc_map.setdefault(row[0], []).append({
                'filename': row[1],
                'created_at': row[2] or '',
            })
        result['documents'] = doc_map

        cursor = await db.execute(
            "SELECT date, note FROM worker_meetings WHERE worker_id = ? ORDER BY id",
            (worker_id,)
        )
        meetings = await cursor.fetchall()
        result['meetings_list'] = [{'date': row[0], 'note': row[1]} for row in meetings]

        return result


async def get_all_workers() -> list[dict]:
    """Получить всех работников (без документов для производительности)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT * FROM workers WHERE name != '__reserved__' ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_worker_documents(worker_id: str) -> dict[str, list[dict]]:
    """Получить документы работника: {doc_type: [{filename, created_at}, ...]}."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT doc_type, filename, created_at FROM worker_documents WHERE worker_id = ? ORDER BY id",
            (worker_id,)
        )
        rows = await cursor.fetchall()
        result: dict[str, list[dict]] = {}
        for row in rows:
            result.setdefault(row[0], []).append({
                'filename': row[1],
                'created_at': row[2] or '',
            })
        return result


async def search_workers(query: str) -> list[dict]:
    """Поиск работников по ФИО."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT * FROM workers WHERE name LIKE ? AND name != '__reserved__' ORDER BY id",
            (f"%{query}%",)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_workers_by_status(status: str) -> list[dict]:
    """Получить работников по статусу (без записей-сирот)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT * FROM workers WHERE status = ? AND name != '__reserved__' ORDER BY id",
            (status,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ─── Управление статусом анкеты ─────────────────────────────────────

async def get_pending_workers() -> list[dict]:
    """Получить работников со статусом pending (без записей-сирот)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT * FROM workers WHERE status = 'pending' AND name != '__reserved__' ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_pending_count() -> int:
    """Количество анкет, ожидающих обработки (без записей-сирот)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM workers WHERE status = 'pending' AND name != '__reserved__'"
        )
        row = await cursor.fetchone()
        return row[0]


async def accept_worker(worker_id: str):
    """Принять анкету — установить статус 'accepted'."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET status = 'accepted', rejection_reasons = '[]' WHERE id = ?",
            (worker_id,)
        )
        await db.commit()


async def reject_worker(worker_id: str, reasons: list[str]):
    """Отклонить анкету с указанием причин."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET status = 'rejected', rejection_reasons = ?, notified_at = NULL WHERE id = ?",
            (json.dumps(reasons, ensure_ascii=False), worker_id)
        )
        await db.commit()


async def resubmit_worker(worker_id: str):
    """Клиент переподал анкету — вернуть статус 'pending'."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET status = 'pending', rejection_reasons = '[]', notified_at = NULL WHERE id = ?",
            (worker_id,)
        )
        await db.commit()


async def get_worker_status(worker_id: str) -> str | None:
    """Получить статус работника."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT status FROM workers WHERE id = ?", (worker_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def mark_notified(worker_id: str):
    """Пометить работника как уведомлённого."""
    from datetime import datetime
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET notified_at = ? WHERE id = ?",
            (datetime.now().isoformat(), worker_id)
        )
        await db.commit()


async def get_unnotified_rejected_workers() -> list[dict]:
    """Получить отклонённых работников, которым ещё не отправлено уведомление (без записей-сирот)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT * FROM workers WHERE status = 'rejected' AND (notified_at IS NULL OR notified_at = '') AND name != '__reserved__'"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Выполнить запрос и вернуть одну строку или None."""
    async with _get_conn() as db:
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None
