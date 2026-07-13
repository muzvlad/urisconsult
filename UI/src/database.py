"""
Слой работы с базой данных: соединения, репозитории, миграции.
"""
from __future__ import annotations
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator
from dataclasses import dataclass

from src.config import get_paths, get_config, WORKER_SCHEMA, WORKER_DOCUMENTS_SCHEMA, WORKER_MEETINGS_SCHEMA, MIGRATIONS, WORKERS_TABLE, WORKER_DOCUMENTS_TABLE, WORKER_MEETINGS_TABLE
from src.models import Worker, WorkerDocument, WorkerMeeting


# ─── Управление соединениями ───

class DatabaseConnection:
    """Управление соединениями с БД."""

    def __init__(self, db_path: Optional[Path] = None, timeout: float = 30.0):
        self.db_path = db_path or get_paths().db_path
        self.timeout = timeout
        self._init_db()

    def _init_db(self) -> None:
        """Инициализация БД и миграции."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(WORKER_SCHEMA)
            conn.execute(WORKER_DOCUMENTS_SCHEMA)
            conn.execute(WORKER_MEETINGS_SCHEMA)

            # Миграции - добавление колонок если их нет
            for col_name, col_def in MIGRATIONS:
                try:
                    conn.execute(f"ALTER TABLE {WORKERS_TABLE} ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass  # Колонка уже существует

            conn.commit()

            # Синхронизация файлов на диске → БД
            self._sync_docs_from_disk(conn)

    def _sync_docs_from_disk(self, conn: sqlite3.Connection) -> None:
        """Сканировать docs_dir и дописать недостающие записи в worker_documents."""
        from src.config import get_paths
        paths = get_paths()
        docs_dir = paths.docs_dir

        if not docs_dir.exists():
            return

        # Маппинг префиксов файлов → doc_type (из конфига бота или дефолтный)
        prefix_to_doc = {}
        try:
            from src.config import get_document_config
            flows, _, _ = get_document_config()
            for cat_docs in flows.values():
                for doc in cat_docs:
                    prefix_to_doc[doc.prefix] = doc.key
        except Exception:
            pass

        # Фоллбэк — дефолтный маппинг если конфиг не загрузился
        if not prefix_to_doc:
            prefix_to_doc = {
                'photo': 'photo',
                'pas': 'passport',
                'pat': 'patent_patent',
                'snils': 'patent_snils',
                'reg': 'patent_registration',
                'mig': 'patent_migration_card',
                'dms': 'patent_dms',
                'inn': 'patent_inn',
                'chek': 'patent_receipt',
                'lang': 'patent_language_cert',
                'bank': 'patent_bank_details',
                'dactyl': 'patent_fingerprint_card',
                'propiska': 'russia_passport_propiska',
                'edu': 'russia_education_doc',
                'trud': 'russia_work_book',
                'voen': 'russia_military_doc',
                'vnzh': 'vnzh_vnzh',
            }

        # Все worker_id из БД
        worker_ids = {row[0] for row in conn.execute(f"SELECT id FROM {WORKERS_TABLE}").fetchall()}

        added = 0
        for worker_id in worker_ids:
            worker_dir = docs_dir / worker_id
            if not worker_dir.exists():
                continue

            existing = {
                row[0] for row in conn.execute(
                    f"SELECT doc_type FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ?",
                    (worker_id,)
                ).fetchall()
            }

            for filename in worker_dir.iterdir():
                if filename.name.startswith('.') or filename.name.startswith('temp_'):
                    continue
                prefix = filename.stem
                doc_type = prefix_to_doc.get(prefix)
                if doc_type and doc_type not in existing:
                    conn.execute(
                        f"INSERT OR IGNORE INTO {WORKER_DOCUMENTS_TABLE} (worker_id, doc_type, filename) VALUES (?, ?, ?)",
                        (worker_id, doc_type, filename.name)
                    )
                    added += 1

        if added:
            conn.commit()

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Контекстный менеджер для соединения."""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Выполнить запрос и вернуть курсор."""
        with self.get_connection() as conn:
            return conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self.get_connection() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            return conn.execute(sql, params).fetchall()


# ─── Репозитории ───

class WorkerRepository:
    """Репозиторий для работы с сотрудниками."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or DatabaseConnection()

    def get_all(self, order_by: str = "id") -> List[Worker]:
        sql = f"SELECT * FROM {WORKERS_TABLE} ORDER BY {order_by}"
        rows = self.db.fetchall(sql)
        return [Worker.from_row(row) for row in rows]

    def get_by_id(self, worker_id: str) -> Optional[Worker]:
        sql = f"SELECT * FROM {WORKERS_TABLE} WHERE id = ?"
        row = self.db.fetchone(sql, (worker_id,))
        return Worker.from_row(row) if row else None

    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Worker]:
        """Поиск по ФИО и другим полям."""
        if fields is None:
            fields = ["name", "id", "phone_main", "email", "position", "object"]

        conditions = " OR ".join([f"{f} LIKE ?" for f in fields])
        sql = f"SELECT * FROM {WORKERS_TABLE} WHERE {conditions} ORDER BY id"
        params = tuple(f"%{query}%" for _ in fields)
        rows = self.db.fetchall(sql, params)
        return [Worker.from_row(row) for row in rows]

    def get_by_status(self, status: str) -> List[Worker]:
        sql = f"SELECT * FROM {WORKERS_TABLE} WHERE status = ? ORDER BY created_at DESC"
        rows = self.db.fetchall(sql, (status,))
        return [Worker.from_row(row) for row in rows]

    def get_pending(self) -> List[Worker]:
        return self.get_by_status("pending")

    def get_accepted(self) -> List[Worker]:
        return self.get_by_status("accepted")

    def get_rejected(self) -> List[Worker]:
        return self.get_by_status("rejected")

    def count_by_status(self, status: str) -> int:
        sql = f"SELECT COUNT(*) FROM {WORKERS_TABLE} WHERE status = ?"
        row = self.db.fetchone(sql, (status,))
        return row[0] if row else 0

    def count_pending(self) -> int:
        return self.count_by_status("pending")

    def update_status(self, worker_id: str, status: str, reasons: Optional[List[str]] = None) -> bool:
        """Обновить статус сотрудника."""
        reasons_json = json.dumps(reasons or [], ensure_ascii=False)
        # При отклонении сбрасываем notified_at, чтобы бот отправил уведомление
        notified_at = "NULL" if status == "rejected" else None
        if status == "rejected":
            sql = f"UPDATE {WORKERS_TABLE} SET status = ?, rejection_reasons = ?, notified_at = NULL WHERE id = ?"
            params = (status, reasons_json, worker_id)
        else:
            sql = f"UPDATE {WORKERS_TABLE} SET status = ?, rejection_reasons = ? WHERE id = ?"
            params = (status, reasons_json, worker_id)
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount > 0

    def accept(self, worker_id: str) -> bool:
        return self.update_status(worker_id, "accepted", [])

    def reject(self, worker_id: str, reasons: List[str]) -> bool:
        return self.update_status(worker_id, "rejected", reasons)

    def create(self, worker: Worker) -> bool:
        """Создать новую запись."""
        sql = f"""
        INSERT INTO {WORKERS_TABLE} (
            id, name, citizenship, gender, position, object, object_address,
            manager, phone_main, phone_additional, email, date, registration,
            marital_status, relatives_json, telegram_id, telegram_username,
            created_at, status, rejection_reasons
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = worker.to_dict()
        data["created_at"] = data.get("created_at") or datetime.now().isoformat()
        try:
            with self.db.get_connection() as conn:
                conn.execute(sql, tuple(data.values()))
            return True
        except sqlite3.IntegrityError:
            return False

    def update(self, worker: Worker) -> bool:
        """Обновить запись."""
        sql = f"""
        UPDATE {WORKERS_TABLE} SET
            name=?, citizenship=?, gender=?, position=?, object=?, object_address=?,
            manager=?, phone_main=?, phone_additional=?, email=?, date=?, registration=?,
            marital_status=?, relatives_json=?, telegram_id=?, telegram_username=?,
            status=?, rejection_reasons=?
        WHERE id=?
        """
        data = worker.to_dict()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(sql, (
                    data["name"], data["citizenship"], data["gender"], data["position"],
                    data["object"], data["object_address"], data["manager"],
                    data["phone_main"], data["phone_additional"], data["email"],
                    data["date"], data["registration"], data["marital_status"],
                    data["relatives_json"], data["telegram_id"], data["telegram_username"],
                    data["status"], data["rejection_reasons"], data["id"]
                ))
            return cursor.rowcount > 0
        except Exception:
            return False

    def delete_worker(self, worker_id: str) -> bool:
        """Полностью удалить сотрудника: БД + файлы документов."""
        import os, glob
        from src.config import get_paths

        paths = get_paths()

        # Удаляем документы из БД
        self.db.execute(f"DELETE FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ?", (worker_id,))
        self.db.execute(f"DELETE FROM {WORKER_MEETINGS_TABLE} WHERE worker_id = ?", (worker_id,))

        # Удаляем файлы документов с диска
        docs_dir = paths.docs_dir
        if docs_dir.exists():
            for pattern in [f"*_{worker_id}.*", f"*_{worker_id}_*"]:
                for f in docs_dir.glob(pattern):
                    try:
                        f.unlink()
                    except OSError:
                        pass

        # Удаляем сотрудника
        sql = f"DELETE FROM {WORKERS_TABLE} WHERE id = ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (worker_id,))
            return cursor.rowcount > 0


class DocumentRepository:
    """Репозиторий для документов сотрудников."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or DatabaseConnection()

    def get_by_worker(self, worker_id: str) -> Dict[str, str]:
        """Получить все документы сотрудника: {doc_type: filename}."""
        sql = f"SELECT doc_type, filename FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ?"
        rows = self.db.fetchall(sql, (worker_id,))
        return {row["doc_type"]: row["filename"] for row in rows}

    def get_document(self, worker_id: str, doc_type: str) -> Optional[str]:
        sql = f"SELECT filename FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ? AND doc_type = ?"
        row = self.db.fetchone(sql, (worker_id, doc_type))
        return row["filename"] if row else None

    def add(self, worker_id: str, doc_type: str, filename: str) -> bool:
        sql = f"""
        INSERT OR REPLACE INTO {WORKER_DOCUMENTS_TABLE} (worker_id, doc_type, filename)
        VALUES (?, ?, ?)
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(sql, (worker_id, doc_type, filename))
            return True
        except Exception:
            return False

    def delete(self, worker_id: str, doc_type: str) -> bool:
        sql = f"DELETE FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ? AND doc_type = ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (worker_id, doc_type))
            return cursor.rowcount > 0

    def clear_worker(self, worker_id: str) -> bool:
        sql = f"DELETE FROM {WORKER_DOCUMENTS_TABLE} WHERE worker_id = ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (worker_id,))
            return cursor.rowcount > 0


class MeetingRepository:
    """Репозиторий для встреч сотрудников."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or DatabaseConnection()

    def get_by_worker(self, worker_id: str) -> List[Dict[str, str]]:
        sql = f"SELECT date, note FROM {WORKER_MEETINGS_TABLE} WHERE worker_id = ? ORDER BY id"
        rows = self.db.fetchall(sql, (worker_id,))
        return [{"date": row["date"] or "", "note": row["note"] or ""} for row in rows]

    def add(self, worker_id: str, date: str, note: str) -> bool:
        sql = f"INSERT INTO {WORKER_MEETINGS_TABLE} (worker_id, date, note) VALUES (?, ?, ?)"
        try:
            with self.db.get_connection() as conn:
                conn.execute(sql, (worker_id, date, note))
            return True
        except Exception:
            return False


# ─── Фасад для удобства ───

class DatabaseService:
    """Единая точка доступа ко всем репозиториям."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db = DatabaseConnection(db_path)
        self.workers = WorkerRepository(self.db)
        self.documents = DocumentRepository(self.db)
        self.meetings = MeetingRepository(self.db)


# Глобальный экземпляр (ленивая инициализация)
_db_service: Optional[DatabaseService] = None


def get_db_service() -> DatabaseService:
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


def init_db(db_path: Optional[Path] = None) -> None:
    """Инициализация БД (создание таблиц и миграции)."""
    DatabaseConnection(db_path)


# Импорт datetime в конце для избежания циклических импортов
from datetime import datetime