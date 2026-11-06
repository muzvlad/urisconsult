"""
Модели данных для работы с БД.

UI не обращается к SQLite напрямую: данные приходят из API бота
(dict -> Worker через api_client._dict_to_worker).
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class Worker:
    """Модель сотрудника."""
    id: str
    name: str
    citizenship: str = ""
    gender: str = ""
    position: str = ""
    object: str = ""
    customer: str = ""
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
    updated_at: str = ""
    status: str = "pending"
    rejection_reasons: str = "[]"
    legal_entity: str = ""
    hr_status: str = "not_processed"
    hr_status_date: str = ""
    documents_signed: str = "0"
    archived_at: str = ""

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
    def reasons(self) -> List[Dict[str, str]]:
        """Причины отклонения: [{'key', 'comment'}, ...]. Поддерживает старый формат (строки)."""
        try:
            raw = json.loads(self.rejection_reasons) if self.rejection_reasons else []
        except (json.JSONDecodeError, TypeError):
            return []
        result = []
        for r in raw:
            if isinstance(r, dict):
                result.append({'key': r.get('key', ''), 'comment': r.get('comment', '')})
            else:
                result.append({'key': str(r), 'comment': ''})
        return result

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "citizenship": self.citizenship,
            "gender": self.gender,
            "position": self.position,
            "object": self.object,
            "customer": self.customer,
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
            "updated_at": self.updated_at,
            "status": self.status,
            "rejection_reasons": self.rejection_reasons,
            "legal_entity": self.legal_entity,
            "hr_status": self.hr_status,
            "hr_status_date": self.hr_status_date,
            "documents_signed": self.documents_signed,
            "archived_at": self.archived_at,
        }


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