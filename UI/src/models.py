"""
Модели данных для работы с БД.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import sqlite3


@dataclass
class Worker:
    """Модель сотрудника."""
    id: str
    name: str
    citizenship: str = ""
    gender: str = ""
    position: str = ""
    object: str = ""
    object_address: str = ""
    manager: str = ""
    phone_main: str = ""
    phone_additional: str = ""
    email: str = ""
    date: str = ""
    registration: str = ""
    marital_status: str = ""
    relatives_json: str = "[]"
    telegram_id: Optional[int] = None
    telegram_username: str = ""
    created_at: str = ""
    status: str = "pending"
    rejection_reasons: str = "[]"

    # Кэш связанных данных
    _documents: Dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _meetings: List[Dict[str, str]] = field(default_factory=list, init=False, repr=False)

    @property
    def relatives(self) -> List[Dict]:
        try:
            return json.loads(self.relatives_json) if self.relatives_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def reasons(self) -> List[str]:
        try:
            return json.loads(self.rejection_reasons) if self.rejection_reasons else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Worker":
        # Безопасное получение значений из Row (поддержка частичных строк)
        def get(key: str, default: str = "") -> str:
            try:
                val = row[key]
                return val if val is not None else default
            except (KeyError, IndexError):
                return default

        return cls(
            id=get("id"),
            name=get("name"),
            citizenship=get("citizenship"),
            gender=get("gender"),
            position=get("position"),
            object=get("object"),
            object_address=get("object_address"),
            manager=get("manager"),
            phone_main=get("phone_main"),
            phone_additional=get("phone_additional"),
            email=get("email"),
            date=get("date"),
            registration=get("registration"),
            marital_status=get("marital_status"),
            relatives_json=get("relatives_json", "[]"),
            telegram_id=row["telegram_id"] if "telegram_id" in row.keys() else None,
            telegram_username=get("telegram_username"),
            created_at=get("created_at"),
            status=get("status", "pending"),
            rejection_reasons=get("rejection_reasons", "[]"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "citizenship": self.citizenship,
            "gender": self.gender,
            "position": self.position,
            "object": self.object,
            "object_address": self.object_address,
            "manager": self.manager,
            "phone_main": self.phone_main,
            "phone_additional": self.phone_additional,
            "email": self.email,
            "date": self.date,
            "registration": self.registration,
            "marital_status": self.marital_status,
            "relatives_json": self.relatives_json,
            "telegram_id": self.telegram_id,
            "telegram_username": self.telegram_username,
            "created_at": self.created_at,
            "status": self.status,
            "rejection_reasons": self.rejection_reasons,
        }


@dataclass
class WorkerDocument:
    """Документ сотрудника."""
    worker_id: str
    doc_type: str
    filename: str
    created_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkerDocument":
        return cls(
            worker_id=row["worker_id"],
            doc_type=row["doc_type"],
            filename=row["filename"],
            created_at=row["created_at"] or "",
        )


@dataclass
class WorkerMeeting:
    """Встреча сотрудника."""
    worker_id: str
    date: str
    note: str
    created_at: str = ""
    id: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkerMeeting":
        return cls(
            id=row["id"],
            worker_id=row["worker_id"],
            date=row["date"] or "",
            note=row["note"] or "",
            created_at=row["created_at"] or "",
        )


# ─── Статусы ───

class WorkerStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.PENDING, cls.ACCEPTED, cls.REJECTED]

    @classmethod
    def get_display(cls, status: str) -> str:
        from src.config import get_config
        config = get_config()
        icons = config.status_icons
        return f"{icons.get(status, '?')} {status.capitalize()}"

    @classmethod
    def get_color(cls, status: str) -> str:
        from src.config import get_config
        config = get_config()
        return config.status_colors.get(status, "#999")