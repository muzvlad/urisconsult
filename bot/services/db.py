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
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager

from config import DB_PATH, USERS_DIR
from config.documents import DOC_FLOWS, DOC_PREFIXES
from shared import (
    WORKER_SCHEMA, WORKER_DOCUMENTS_SCHEMA, WORKER_MEETINGS_SCHEMA,
    WORKER_NOTES_SCHEMA, now_msk,
)

logger = logging.getLogger(__name__)

# ─── Текущая версия схемы ──────────────────────────────────────────
# ─── Текущая версия схемы ──────────────────────────────────────────
CURRENT_SCHEMA_VERSION = 7

# HR-статусы: внутренний кадровый процесс, клиент их не видит и не меняет.
# notify (Уведомить) и mvd_check (На проверке МВД) ставятся только из UI.
HR_STATUSES = ('not_processed', 'docs_pending', 'employed', 'rejected', 'fired', 'notify', 'mvd_check')

# Служебная запись, резервирующая следующий числовой ID (см. get_next_id).
RESERVED_NAME = '__reserved__'

# Брошенным считается резерв старше этого времени (часов).
RESERVED_TTL_HOURS = 1


def _not_reserved(alias: str = '') -> str:
    """SQL-условие, исключающее служебные записи __reserved__ из выборок."""
    column = f"{alias}.name" if alias else "name"
    return f"{column} != '{RESERVED_NAME}'"


# ─── Соединение ──────────────────────────────────────────────────────

@asynccontextmanager
async def _get_conn():
    """Контекстный менеджер: открывает соединение, отдаёт, закрывает.

    БД может лежать на сетевом ресурсе (бот и UI на разных машинах),
    поэтому транзакции должны быть короткими: commit сразу после пачки
    логически связных изменений, не держать соединение во время сетевых
    вызовов и тяжёлых вычислений. Прямой доступ к SQLite есть только
    здесь — UI работает исключительно через HTTP API.
    """
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    # busy_timeout задаём первым: без него ожидание блокировки идёт 0 мс.
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        await conn.close()


# ─── Инициализация ──────────────────────────────────────────────────

async def _ensure_wal():
    """Перевести БД в режим WAL (один раз на файл БД).

    Режим журнала хранится в файле БД, поэтому переключать его при каждом
    подключении не нужно. Сам PRAGMA требует эксклюзивной блокировки и при
    конкуренции возвращает SQLITE_BUSY, не вызывая busy-handler, поэтому
    переключение повторяем. Работает на отдельном соединении: неудачный
    PRAGMA оставляет соединение в непригодном для записи состоянии.
    """
    import asyncio

    async with _get_conn() as db:
        # fetchall, а не fetchone: курсор должен быть исчерпан, иначе
        # остаётся read-lock, который блокирует переключение в WAL.
        cursor = await db.execute("PRAGMA journal_mode")
        rows = await cursor.fetchall()
        mode = str(rows[0][0]).lower() if rows else ''
        if mode == 'wal':
            return
        for _ in range(25):
            try:
                await db.execute("PRAGMA journal_mode=WAL")
                return
            except sqlite3.OperationalError:
                await asyncio.sleep(0.2)
    logger.warning("Не удалось перевести БД в режим WAL")


async def init_db():
    """Инициализация БД: создание таблиц и миграция по версиям.

    BEGIN IMMEDIATE сериализует инициализацию между процессами: бот и
    API-сервер на разных машинах могут стартовать одновременно на одной
    общей БД, и без явной блокировки миграции выполнялись бы параллельно
    (это давало «database is locked» на свежей БД). Всё выполняется одной
    транзакцией — при сбое изменения откатываются целиком.
    """
    from datetime import timedelta

    # WAL переключаем до BEGIN IMMEDIATE: смена режима журнала
    # невозможна внутри транзакции.
    await _ensure_wal()

    async with _get_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            # Таблицы — единая схема из shared
            await db.execute(WORKER_SCHEMA)
            await db.execute(WORKER_DOCUMENTS_SCHEMA)
            await db.execute(WORKER_MEETINGS_SCHEMA)
            await db.execute(WORKER_NOTES_SCHEMA)

            # Индексы
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_worker ON worker_documents(worker_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wd_type ON worker_documents(doc_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wm_worker ON worker_meetings(worker_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wn_worker ON worker_notes(worker_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_workers_name ON workers(name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_workers_telegram ON workers(telegram_id)")

            # Очистка брошенных резервов: свежие резервы не трогаем, иначе
            # другой процесс мог бы получить уже выданный ID.
            cutoff = (now_msk() - timedelta(hours=RESERVED_TTL_HOURS)).isoformat()
            await db.execute(
                "DELETE FROM workers WHERE name = ? AND (created_at = '' OR created_at < ?)",
                (RESERVED_NAME, cutoff)
            )

            # Версионированные миграции
            cursor = await db.execute("PRAGMA user_version")
            row = await cursor.fetchone()
            current_version = row[0]

            if current_version < CURRENT_SCHEMA_VERSION:
                logger.info("Миграция БД: версия %d → %d", current_version, CURRENT_SCHEMA_VERSION)
                await _run_migrations(db, current_version)
                await db.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
                logger.info("Миграция БД завершена. Текущая версия: %d", CURRENT_SCHEMA_VERSION)

            await db.commit()
        except Exception:
            await db.rollback()
            raise


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
    if from_version < 6:
        await _migrate_v5_to_v6(db)
    if from_version < 7:
        await _migrate_v6_to_v7(db)


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

        meta_fields = doc_columns | {'meetings', 'russia_marital_status', 'russia_relatives'}
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
    except sqlite3.OperationalError:
        pass

    try:
        await db.execute("ALTER TABLE workers ADD COLUMN status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN rejection_reasons TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN updated_at TEXT")
    except sqlite3.OperationalError:
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
    except sqlite3.OperationalError:
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
            created_at TEXT DEFAULT (datetime('now', '+3 hours')),
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

# ─── Миграция v5 → v6: заказчик, UI-поля, уведомления, комментарии ────

async def _migrate_v5_to_v6(db: aiosqlite.Connection):
    """Миграция v5→v6: новые поля анкеты, уведомления о встречах, комментарии."""
    for column, definition in (
        ('customer', 'TEXT'),
        ('legal_entity', 'TEXT'),
        ('hr_status', "TEXT DEFAULT 'not_processed'"),
        ('hr_status_date', 'TEXT'),
        ('archived_at', 'TEXT'),
    ):
        try:
            await db.execute(f"ALTER TABLE workers ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass

    for column in ('notified_at', 'reminded_at'):
        try:
            await db.execute(f"ALTER TABLE worker_meetings ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass

    await db.execute(WORKER_NOTES_SCHEMA)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wn_worker ON worker_notes(worker_id)")

    await db.execute(
        "UPDATE workers SET hr_status = 'not_processed' "
        "WHERE hr_status IS NULL OR hr_status = ''"
    )
    # Старые встречи не должны вызвать рассылку после обновления
    await db.execute(
        "UPDATE worker_meetings SET notified_at = "
        "COALESCE(NULLIF(created_at, ''), datetime('now', '+3 hours')) "
        "WHERE notified_at IS NULL OR notified_at = ''"
    )
    await db.execute(
        "UPDATE worker_meetings SET reminded_at = "
        "COALESCE(NULLIF(created_at, ''), datetime('now', '+3 hours')) "
        "WHERE reminded_at IS NULL OR reminded_at = ''"
    )
    await db.commit()
    logger.info("Миграция v5→v6 завершена")

# ─── Миграция v6 → v7: документы подписаны + новые HR-статусы ─────

async def _migrate_v6_to_v7(db: aiosqlite.Connection):
    """Миграция v6→v7: добавление колонки documents_signed."""
    try:
        await db.execute("ALTER TABLE workers ADD COLUMN documents_signed TEXT DEFAULT '0'")
        logger.info("Миграция v6→v7: добавлена колонка documents_signed")
    except sqlite3.OperationalError:
        pass
    await db.commit()


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
    """Сканировать users/docs/ и дописать недостающие записи в worker_documents.

    Префикс файла не уникален между категориями (snils, reg, bank и т.д.
    повторяются), поэтому сопоставляем файл с типом документа только внутри
    категории самого работника (по citizenship), а не глобально.
    """
    from config import DOCS_DIR

    if not os.path.isdir(DOCS_DIR):
        return

    cursor = await db.execute("SELECT id FROM workers")
    worker_ids = {row[0] for row in await cursor.fetchall()}

    added = 0
    for worker_id in worker_ids:
        worker_dir = os.path.join(DOCS_DIR, worker_id)
        if not os.path.isdir(worker_dir):
            continue

        # Категория работника — нужно знать, какие префиксы ему принадлежат.
        cursor = await db.execute(
            "SELECT citizenship FROM workers WHERE id = ?", (worker_id,)
        )
        row = await cursor.fetchone()
        citizenship = row[0] if row else None
        if citizenship not in DOC_FLOWS:
            continue

        prefix_to_doc = {}
        for doc in DOC_FLOWS[citizenship]:
            prefix_to_doc[doc.prefix] = doc.key

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
    """Получить следующий доступный ID (без race condition).

    ID резервируется служебной записью __reserved__: INSERT падает с
    IntegrityError, если параллельный вызов уже занял тот же номер.
    Резерв перезаписывается реальными данными в save_worker, а брошенные
    резервы (старше RESERVED_TTL_HOURS) чистятся в init_db.
    """

    async with _get_conn() as db:
        for _ in range(100):  # ponytail: не больше 100 попыток
            # fetchall, а не fetchone: курсор должен быть исчерпан, иначе
            # остаётся read-lock, и следующий INSERT идёт как upgrade
            # read→write — SQLite отдаёт «database is locked» без retry.
            cursor = await db.execute("SELECT id FROM workers ORDER BY CAST(id AS INTEGER) DESC LIMIT 1")
            rows = await cursor.fetchall()
            row = rows[0] if rows else None
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
                    "INSERT INTO workers (id, name, created_at) VALUES (?, ?, ?)",
                    (next_id_str, RESERVED_NAME, now_msk().isoformat())
                )
                await db.commit()
                logger.debug("get_next_id: создана запись-заглушка id=%s", next_id_str)
                return next_id_str
            except sqlite3.IntegrityError:
                # ID занят параллельным вызовом — пробуем следующий
                continue
        raise RuntimeError("Не удалось сгенерировать уникальный ID после 100 попыток")


async def save_worker(data: dict) -> str:
    """Сохранить работника в БД (INSERT или UPDATE по id)."""
    async with _get_conn() as db:
        worker_id = data.get('id', '')

        # Гарантируем даты: created_at только при INSERT, updated_at при каждом сохранении
        now = now_msk().isoformat()
        created_at = data.get('created_at') or now
        updated_at = data.get('updated_at') or now

        personal_keys = [
            'id', 'name', 'citizenship', 'gender', 'position', 'object',
            'customer', 'object_address', 'manager', 'phone_main', 'phone_additional',
            'date', 'registration', 'marital_status', 'relatives_json',
            'telegram_id', 'telegram_username',
        ]

        personal = {k: data.get(k, '' if k != 'telegram_id' else None) for k in personal_keys}
        personal['created_at'] = created_at
        personal['updated_at'] = updated_at

        placeholders = ', '.join(['?'] * len(personal))
        cols = ', '.join(personal.keys())
        # В UPDATE идут только те колонки, что реально передали: иначе
        # частичное обновление затирает поля, которых не было в data
        update_cols = [k for k in personal.keys()
                       if k not in ('id', 'created_at') and (k in data or k == 'updated_at')]
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
                            "INSERT INTO worker_meetings (worker_id, date, note, created_at) "
                            "VALUES (?, ?, ?, ?)",
                            (worker_id, m.get('date', ''),
                             m.get('note', m.get('description', '')), now_msk().isoformat())
                        )

        await db.commit()
        return worker_id


async def save_documents(worker_id: str, doc_files: dict[str, str | list[str]]):
    """Сохранить документы работника. doc_files = {doc_type: filename | [filename, ...]}.

    created_at первой загрузки не перезаписывается: если файл с тем же именем
    уже был загружен, дата сохраняется (спека 051).
    """
    # created_at пишем явно московским временем: DEFAULT CURRENT_TIMESTAMP
    # в SQLite отдаёт UTC, из-за чего «Залит:» показывалось бы на 3 часа раньше.
    now = now_msk().isoformat()
    async with _get_conn() as db:
        # Запоминаем дату первой загрузки по каждому имени файла
        cursor = await db.execute(
            "SELECT doc_type, filename, created_at FROM worker_documents WHERE worker_id = ?",
            (worker_id,)
        )
        first_loaded = {(row[0], row[1]): row[2] for row in await cursor.fetchall()}

        for doc_type in doc_files:
            await db.execute(
                "DELETE FROM worker_documents WHERE worker_id = ? AND doc_type = ?",
                (worker_id, doc_type)
            )
        for doc_type, value in doc_files.items():
            filenames = value if isinstance(value, list) else [value]
            for filename in filenames:
                if filename:
                    created_at = first_loaded.get((doc_type, filename)) or now
                    await db.execute(
                        "INSERT INTO worker_documents (worker_id, doc_type, filename, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (worker_id, doc_type, filename, created_at)
                    )
        await db.commit()


async def add_document(worker_id: str, doc_type: str, filename: str) -> bool:
    """Добавить запись о документе, если её ещё нет."""
    if not filename:
        return False
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT id FROM worker_documents WHERE worker_id = ? AND doc_type = ? AND filename = ?",
            (worker_id, doc_type, filename)
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO worker_documents (worker_id, doc_type, filename, created_at) "
            "VALUES (?, ?, ?, ?)",
            (worker_id, doc_type, filename, now_msk().isoformat())
        )
        await db.commit()
        return True


async def replace_document(worker_id: str, doc_type: str, old_filename: str) -> bool:
    """Замена документа (перезаливка из UI): имя файла не меняется,
    содержимое перезаписывается, а created_at обновляется — в таблице
    нет updated_at, поэтому дата замены фиксируется в created_at.
    """
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE worker_documents SET created_at = ? "
            "WHERE worker_id = ? AND doc_type = ? AND filename = ?",
            (now_msk().isoformat(), worker_id, doc_type, old_filename)
        )
        await db.commit()
        return cursor.rowcount > 0


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


# Колонки для списочных выборок: без тяжёлых JSON (relatives_json) и без email
# (email убран из анкеты по спеке 014). rejection_reasons нужны для экспорта
# карточек в PDF, поэтому остаются.
WORKER_LIST_COLUMNS = (
    "id, name, citizenship, gender, position, object, customer, object_address, "
    "manager, phone_main, phone_additional, date, registration, marital_status, "
    "telegram_id, telegram_username, created_at, updated_at, status, "
    "rejection_reasons, legal_entity, hr_status, hr_status_date, "
    "documents_signed, archived_at"
)


def _worker_filters(archived: str = '0', date_from: str | None = None,
                    date_to: str | None = None) -> tuple[str, list]:
    """Общие условия выборки анкет: архив и период по created_at."""
    clauses = [_not_reserved()]
    params: list = []
    if archived == '0':
        clauses.append("(archived_at IS NULL OR archived_at = '')")
    elif archived == '1':
        clauses.append("archived_at IS NOT NULL AND archived_at != ''")
    if date_from:
        clauses.append("date(created_at) >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date(created_at) <= ?")
        params.append(date_to)
    return " AND ".join(clauses), params


async def get_all_workers(archived: str = '0', date_from: str | None = None,
                          date_to: str | None = None) -> list[dict]:
    """Получить всех работников (без документов для производительности)."""
    where, params = _worker_filters(archived, date_from, date_to)
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT {WORKER_LIST_COLUMNS} FROM workers WHERE {where} ORDER BY id", params
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


async def search_workers(query: str, archived: str = '0',
                         date_from: str | None = None,
                         date_to: str | None = None) -> list[dict]:
    """Поиск работников по ФИО."""
    where, params = _worker_filters(archived, date_from, date_to)
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT {WORKER_LIST_COLUMNS} FROM workers WHERE name LIKE ? AND {where} ORDER BY id",
            [f"%{query}%", *params]
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_workers_by_status(status: str, archived: str = '0',
                                date_from: str | None = None,
                                date_to: str | None = None) -> list[dict]:
    """Получить работников по статусу (без записей-сирот)."""
    where, params = _worker_filters(archived, date_from, date_to)
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT {WORKER_LIST_COLUMNS} FROM workers WHERE status = ? AND {where} ORDER BY id",
            [status, *params]
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ─── Управление статусом анкеты ─────────────────────────────────────

async def get_pending_workers() -> list[dict]:
    """Получить работников со статусом pending (без записей-сирот и архива)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT * FROM workers WHERE status = 'pending' AND {_not_reserved()} "
            "AND (archived_at IS NULL OR archived_at = '') ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_pending_count() -> int:
    """Количество анкет, ожидающих обработки (без записей-сирот и архива)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM workers WHERE status = 'pending' AND {_not_reserved()} "
            "AND (archived_at IS NULL OR archived_at = '')"
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


async def reject_worker(worker_id: str, reasons: list[str] | list[dict]):
    """Отклонить анкету с указанием причин. reasons = [str | {key, comment}]."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET status = 'rejected', rejection_reasons = ?, notified_at = NULL WHERE id = ?",
            (json.dumps(reasons, ensure_ascii=False), worker_id)
        )
        await db.commit()


async def resubmit_worker(worker_id: str):
    """Клиент переподал анкету — вернуть статус 'pending' и убрать из архива."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET status = 'pending', rejection_reasons = '[]', "
            "notified_at = NULL, archived_at = NULL WHERE id = ?",
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
    async with _get_conn() as db:
        await db.execute(
            "UPDATE workers SET notified_at = ? WHERE id = ?",
            (now_msk().isoformat(), worker_id)
        )
        await db.commit()


async def get_unnotified_rejected_workers() -> list[dict]:
    """Получить отклонённых работников, которым ещё не отправлено уведомление (без записей-сирот)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            f"SELECT * FROM workers WHERE status = 'rejected' "
            f"AND (notified_at IS NULL OR notified_at = '') AND {_not_reserved()}"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ─── UI-поля анкеты ──────────────────────────────────────────────────

async def set_legal_entity(worker_id: str, value: str) -> bool:
    """Сохранить юридическое лицо (только UI)."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE workers SET legal_entity = ?, updated_at = ? WHERE id = ?",
            (value, now_msk().isoformat(), worker_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def set_hr_status(worker_id: str, status: str, date_value: str | None) -> bool:
    """Сохранить HR-статус. Для employed/fired дата обязательна."""
    if status not in HR_STATUSES:
        return False
    if status in ('employed', 'fired'):
        if not date_value or not _valid_hr_date_local(date_value):
            return False
    if date_value is not None and not _valid_hr_date_local(date_value):
        return False
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE workers SET hr_status = ?, hr_status_date = ?, updated_at = ? WHERE id = ?",
            (status, date_value or '', now_msk().isoformat(), worker_id)
        )
        await db.commit()
        return cursor.rowcount > 0


def _valid_hr_date_local(value: str) -> bool:
    """Проверить дату в формате ДД.ММ.ГГГГ или YYYY-MM-DD."""
    import re
    from datetime import datetime
    if not isinstance(value, str) or not value:
        return False
    for fmt, pattern in (('%d.%m.%Y', r'\d{2}\.\d{2}\.\d{4}'),
                         ('%Y-%m-%d', r'\d{4}-\d{2}-\d{2}')):
        if re.fullmatch(pattern, value):
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                return False
    return False


async def set_documents_signed(worker_id: str, value: str) -> bool:
    """Отметить/снять галочку «Документы подписаны» ('1'/'0').

    Внутренний HR-флаг: ставится только из UI, клиент его не видит.
    """
    if value not in ('0', '1'):
        return False
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE workers SET documents_signed = ?, updated_at = ? WHERE id = ?",
            (value, now_msk().isoformat(), worker_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def archive_worker(worker_id: str) -> bool:
    """Поместить анкету в архив (мягкое удаление)."""
    now = now_msk().isoformat()
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE workers SET archived_at = ?, updated_at = ? WHERE id = ?",
            (now, now, worker_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def unarchive_worker(worker_id: str) -> bool:
    """Вернуть анкету из архива."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "UPDATE workers SET archived_at = NULL, updated_at = ? WHERE id = ?",
            (now_msk().isoformat(), worker_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_worker(worker_id: str) -> bool:
    """Удалить анкету и связанные записи."""
    async with _get_conn() as db:
        await db.execute("DELETE FROM worker_notes WHERE worker_id = ?", (worker_id,))
        await db.execute("DELETE FROM worker_documents WHERE worker_id = ?", (worker_id,))
        await db.execute("DELETE FROM worker_meetings WHERE worker_id = ?", (worker_id,))
        cursor = await db.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        await db.commit()
        return cursor.rowcount > 0


# ─── Встречи и уведомления ───────────────────────────────────────────

async def add_meeting(worker_id: str, date: str, note: str) -> int:
    """Добавить встречу, вернуть id."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "INSERT INTO worker_meetings (worker_id, date, note, created_at) "
            "VALUES (?, ?, ?, ?)",
            (worker_id, date, note, now_msk().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_unnotified_meetings() -> list[dict]:
    """Встречи без уведомления по активным анкетам."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT m.id, m.worker_id, m.date, m.note, w.name AS worker_name, "
            "w.object, w.telegram_id "
            "FROM worker_meetings m JOIN workers w ON w.id = m.worker_id "
            "WHERE (m.notified_at IS NULL OR m.notified_at = '') "
            f"AND {_not_reserved('w')} "
            "AND (w.archived_at IS NULL OR w.archived_at = '') ORDER BY m.id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_meetings_to_remind() -> list[dict]:
    """Встречи, по которым уже отправлено уведомление, но нет напоминания."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT m.id, m.worker_id, m.date, m.note, w.name AS worker_name, "
            "w.object, w.telegram_id "
            "FROM worker_meetings m JOIN workers w ON w.id = m.worker_id "
            "WHERE (m.notified_at IS NOT NULL AND m.notified_at != '') "
            "AND (m.reminded_at IS NULL OR m.reminded_at = '') "
            f"AND {_not_reserved('w')} "
            "AND (w.archived_at IS NULL OR w.archived_at = '') ORDER BY m.id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_meeting_notified(meeting_id: int, value: str) -> None:
    """Отметить уведомление о встрече."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE worker_meetings SET notified_at = ? WHERE id = ?",
            (value, meeting_id)
        )
        await db.commit()


async def mark_meeting_reminded(meeting_id: int, value: str) -> None:
    """Отметить напоминание о встрече."""
    async with _get_conn() as db:
        await db.execute(
            "UPDATE worker_meetings SET reminded_at = ? WHERE id = ?",
            (value, meeting_id)
        )
        await db.commit()


async def get_meetings(worker_id: str) -> list[dict]:
    """Встречи работника в порядке добавления."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT id, date, note, created_at FROM worker_meetings WHERE worker_id = ? ORDER BY id",
            (worker_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ─── Комментарии ─────────────────────────────────────────────────────

async def get_worker_notes(worker_id: str) -> list[dict]:
    """Комментарии анкеты в порядке добавления."""
    async with _get_conn() as db:
        cursor = await db.execute(
            "SELECT id, text, created_at, updated_at FROM worker_notes "
            "WHERE worker_id = ? ORDER BY id", (worker_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def add_worker_note(worker_id: str, text: str) -> int | None:
    """Добавить комментарий. Пустой текст не сохраняется."""
    text = text.strip()
    if not text:
        return None
    now = now_msk().isoformat()
    async with _get_conn() as db:
        cursor = await db.execute(
            "INSERT INTO worker_notes (worker_id, text, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)", (worker_id, text, now, now)
        )
        await db.commit()
        return cursor.lastrowid


async def update_worker_note(note_id: int, text: str,
                             worker_id: str | None = None) -> bool:
    """Изменить комментарий. Пустой текст не сохраняется."""
    text = text.strip()
    if not text:
        return False
    sql = "UPDATE worker_notes SET text = ?, updated_at = ? WHERE id = ?"
    params: list = [text, now_msk().isoformat(), note_id]
    if worker_id is not None:
        sql += " AND worker_id = ?"
        params.append(worker_id)
    async with _get_conn() as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.rowcount > 0


async def delete_worker_note(note_id: int, worker_id: str | None = None) -> bool:
    """Удалить комментарий."""
    sql = "DELETE FROM worker_notes WHERE id = ?"
    params: list = [note_id]
    if worker_id is not None:
        sql += " AND worker_id = ?"
        params.append(worker_id)
    async with _get_conn() as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.rowcount > 0


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Выполнить запрос и вернуть одну строку или None."""
    async with _get_conn() as db:
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None
