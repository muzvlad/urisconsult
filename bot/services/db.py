"""
Сервис для работы с SQLite базой данных
"""
import os
import json
import aiosqlite
from config import DB_PATH, USERS_DIR

_db = None


async def get_db() -> aiosqlite.Connection:
    """Получить соединение с БД (синглтон)"""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
    return _db


async def close_db():
    """Закрыть соединение с БД"""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db():
    """Инициализация БД: создание таблицы и миграция из JSON"""
    db = await get_db()
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
            photo TEXT,
            passport TEXT,
            patent_snils TEXT,
            patent_registration TEXT,
            patent_migration_card TEXT,
            patent_dms TEXT,
            patent_patent TEXT,
            patent_inn TEXT,
            patent_receipt TEXT,
            patent_language_cert TEXT,
            patent_bank_details TEXT,
            patent_fingerprint_card TEXT,
            student_snils TEXT,
            student_registration TEXT,
            student_migration_card TEXT,
            student_dms TEXT,
            student_inn TEXT,
            student_fingerprint_card TEXT,
            student_university_cert TEXT,
            student_bank_details TEXT,
            eaeas_registration TEXT,
            eaeas_migration_card TEXT,
            eaeas_dms TEXT,
            eaeas_inn TEXT,
            eaeas_snils TEXT,
            eaeas_fingerprint_card TEXT,
            eaeas_bank_details TEXT,
            rvp_migration_card TEXT,
            rvp_dms_oms TEXT,
            rvp_inn TEXT,
            rvp_snils TEXT,
            rvp_bank_details TEXT,
            vnzh_migration_card TEXT,
            vnzh_vnzh TEXT,
            vnzh_dms_oms TEXT,
            vnzh_inn TEXT,
            vnzh_snils TEXT,
            vnzh_work_book TEXT,
            vnzh_bank_details TEXT,
            russia_passport_propiska TEXT,
            russia_propiska TEXT,
            russia_inn TEXT,
            russia_snils TEXT,
            russia_education_doc TEXT,
            russia_work_book TEXT,
            russia_military_doc TEXT,
            russia_marital_status TEXT,
            russia_relatives TEXT DEFAULT '[]',
            registration TEXT,
            telegram_id INTEGER,
            telegram_username TEXT,
            created_at TEXT,
            meetings TEXT DEFAULT '[]'
        )
    """)
    await db.commit()
    await _migrate_json(db)


async def _migrate_json(db: aiosqlite.Connection):
    """Миграция существующих JSON-файлов в БД"""
    if not os.path.exists(USERS_DIR):
        return

    json_files = [f for f in os.listdir(USERS_DIR) if f.endswith('.json')]
    if not json_files:
        return

    existing = await db.execute("SELECT id FROM workers")
    existing_ids = {row[0] async for row in existing}
    if existing_ids:
        return

    for filename in json_files:
        filepath = os.path.join(USERS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            worker_id = data.get('id', '')
            if not worker_id or worker_id in existing_ids:
                continue
            await db.execute("""
                INSERT OR IGNORE INTO workers
                (id, name, citizenship, gender, position, object, object_address,
                 manager, phone_main, phone_additional, email, date,
                 photo, passport, patent_snils, patent_registration, patent_migration_card,
                 patent_dms, patent_patent, patent_inn, patent_receipt,
                 patent_language_cert, patent_bank_details, patent_fingerprint_card,
                 student_snils, student_registration, student_migration_card,
                 student_dms, student_inn, student_fingerprint_card,
                 student_university_cert, student_bank_details,
                 eaeas_registration, eaeas_migration_card, eaeas_dms,
                 eaeas_inn, eaeas_snils, eaeas_fingerprint_card, eaeas_bank_details,
                 rvp_migration_card, rvp_dms_oms, rvp_inn, rvp_snils, rvp_bank_details,
                 vnzh_migration_card, vnzh_vnzh, vnzh_dms_oms, vnzh_inn, vnzh_snils,
                 vnzh_work_book, vnzh_bank_details,
                 registration,
                 telegram_id, telegram_username, created_at, meetings)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                worker_id,
                data.get('name', ''),
                data.get('citizenship', ''),
                data.get('gender', ''),
                data.get('position', ''),
                data.get('object', ''),
                data.get('object_address', ''),
                data.get('manager', ''),
                data.get('phone_main', ''),
                data.get('phone_additional', ''),
                data.get('email', ''),
                data.get('date', ''),
                data.get('photo', ''),
                data.get('\u041f\u0430\u0441\u043f\u043e\u0440\u0442', ''),
                data.get('patent_snils', ''),
                data.get('patent_registration', ''),
                data.get('patent_migration_card', ''),
                data.get('patent_dms', ''),
                data.get('\u041f\u0430\u0442\u0435\u043d\u0442', ''),
                data.get('patent_inn', ''),
                data.get('patent_receipt', ''),
                data.get('patent_language_cert', ''),
                data.get('patent_bank_details', ''),
                data.get('patent_fingerprint_card', ''),
                data.get('student_snils', ''),
                data.get('student_registration', ''),
                data.get('student_migration_card', ''),
                data.get('student_dms', ''),
                data.get('student_inn', ''),
                data.get('student_fingerprint_card', ''),
                data.get('student_university_cert', ''),
                data.get('student_bank_details', ''),
                data.get('eaeas_registration', ''),
                data.get('eaeas_migration_card', ''),
                data.get('eaeas_dms', ''),
                data.get('eaeas_inn', ''),
                data.get('eaeas_snils', ''),
                data.get('eaeas_fingerprint_card', ''),
                data.get('eaeas_bank_details', ''),
                data.get('rvp_migration_card', ''),
                data.get('rvp_dms_oms', ''),
                data.get('rvp_inn', ''),
                data.get('rvp_snils', ''),
                data.get('rvp_bank_details', ''),
                data.get('vnzh_migration_card', ''),
                data.get('vnzh_vnzh', ''),
                data.get('vnzh_dms_oms', ''),
                data.get('vnzh_inn', ''),
                data.get('vnzh_snils', ''),
                data.get('vnzh_work_book', ''),
                data.get('vnzh_bank_details', ''),
                data.get('\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f', ''),
                data.get('telegram_id'),
                data.get('telegram_username', ''),
                data.get('created_at', ''),
                json.dumps(data.get('meetings', []), ensure_ascii=False)
            ))
            existing_ids.add(worker_id)
        except (json.JSONDecodeError, KeyError):
            continue

    await db.commit()


async def get_next_id() -> str:
    """Получить следующий доступный ID"""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM workers")
    rows = await cursor.fetchall()
    if not rows:
        return "00001"
    ids = [int(row[0]) for row in rows]
    next_id = max(ids) + 1
    return str(next_id).zfill(5)


async def save_worker(data: dict) -> str:
    """
    Сохранить работника в БД (INSERT или UPDATE по id).

    Returns: worker_id
    """
    db = await get_db()
    worker_id = data.get('id', '')
    await db.execute("""
        INSERT OR REPLACE INTO workers
        (id, name, citizenship, gender, position, object, object_address,
         manager, phone_main, phone_additional, email, date,
         photo, passport, patent_snils, patent_registration, patent_migration_card,
         patent_dms, patent_patent, patent_inn, patent_receipt,
         patent_language_cert, patent_bank_details, patent_fingerprint_card,
         student_snils, student_registration, student_migration_card,
         student_dms, student_inn, student_fingerprint_card,
         student_university_cert, student_bank_details,
         eaeas_registration, eaeas_migration_card, eaeas_dms,
         eaeas_inn, eaeas_snils, eaeas_fingerprint_card, eaeas_bank_details,
         rvp_migration_card, rvp_dms_oms, rvp_inn, rvp_snils, rvp_bank_details,
         vnzh_migration_card, vnzh_vnzh, vnzh_dms_oms, vnzh_inn, vnzh_snils,
         vnzh_work_book, vnzh_bank_details,
         russia_passport_propiska, russia_propiska, russia_inn, russia_snils,
         russia_education_doc, russia_work_book, russia_military_doc,
         russia_marital_status, russia_relatives,
         registration,
         telegram_id, telegram_username, created_at, meetings)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        worker_id,
        data.get('name', ''),
        data.get('citizenship', ''),
        data.get('gender', ''),
        data.get('position', ''),
        data.get('object', ''),
        data.get('object_address', ''),
        data.get('manager', ''),
        data.get('phone_main', ''),
        data.get('phone_additional', ''),
        data.get('email', ''),
        data.get('date', ''),
        data.get('photo', ''),
        data.get('passport', ''),
        data.get('patent_snils', ''),
        data.get('patent_registration', ''),
        data.get('patent_migration_card', ''),
        data.get('patent_dms', ''),
        data.get('patent_patent', ''),
        data.get('patent_inn', ''),
        data.get('patent_receipt', ''),
        data.get('patent_language_cert', ''),
        data.get('patent_bank_details', ''),
        data.get('patent_fingerprint_card', ''),
        data.get('student_snils', ''),
        data.get('student_registration', ''),
        data.get('student_migration_card', ''),
        data.get('student_dms', ''),
        data.get('student_inn', ''),
        data.get('student_fingerprint_card', ''),
        data.get('student_university_cert', ''),
        data.get('student_bank_details', ''),
        data.get('eaeas_registration', ''),
        data.get('eaeas_migration_card', ''),
        data.get('eaeas_dms', ''),
        data.get('eaeas_inn', ''),
        data.get('eaeas_snils', ''),
        data.get('eaeas_fingerprint_card', ''),
        data.get('eaeas_bank_details', ''),
        data.get('rvp_migration_card', ''),
        data.get('rvp_dms_oms', ''),
        data.get('rvp_inn', ''),
        data.get('rvp_snils', ''),
        data.get('rvp_bank_details', ''),
        data.get('vnzh_migration_card', ''),
        data.get('vnzh_vnzh', ''),
        data.get('vnzh_dms_oms', ''),
        data.get('vnzh_inn', ''),
        data.get('vnzh_snils', ''),
        data.get('vnzh_work_book', ''),
        data.get('vnzh_bank_details', ''),
        data.get('russia_passport_propiska', ''),
        data.get('russia_propiska', ''),
        data.get('russia_inn', ''),
        data.get('russia_snils', ''),
        data.get('russia_education_doc', ''),
        data.get('russia_work_book', ''),
        data.get('russia_military_doc', ''),
        data.get('russia_marital_status', ''),
        json.dumps(data.get('russia_relatives_list', []), ensure_ascii=False),
        data.get('registration', ''),
        data.get('telegram_id'),
        data.get('telegram_username', ''),
        data.get('created_at', ''),
        json.dumps(data.get('meetings', []), ensure_ascii=False)
    ))
    await db.commit()
    return worker_id


async def get_worker(worker_id: str) -> dict | None:
    """Получить работника по ID"""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def get_all_workers() -> list[dict]:
    """Получить всех работников"""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM workers ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
