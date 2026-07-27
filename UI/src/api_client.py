"""
HTTP client for the URIS Consult API server.
Uses only stdlib: urllib, json, pathlib.
"""
from __future__ import annotations
import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.models import Worker

logger = logging.getLogger(__name__)


class APIClient:
    """Drop-in replacement for DatabaseService that talks to the API server."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._cache_dir = Path(os.path.expanduser("~")) / ".urisconsult_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def _get(self, path: str) -> dict | list | None:
        url = self.base_url + path
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("GET %s → %s", url, e.code)
            return None
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _put(self, path: str, data: dict = None) -> dict:
        url = self.base_url + path
        body = json.dumps(data or {}).encode()
        try:
            req = urllib.request.Request(url, data=body, method="PUT")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("PUT %s → %s", url, e.code)
            return {}
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _delete(self, path: str) -> dict:
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("DELETE %s → %s", url, e.code)
            return {}
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _post(self, path: str, data: dict) -> dict:
        url = self.base_url + path
        body = json.dumps(data).encode()
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("POST %s → %s", url, e.code)
            return {}
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    # ── Workers ──

    def get_workers(self, status: Optional[str] = None, search: Optional[str] = None) -> List[Worker]:
        params = []
        if status:
            params.append(f"status={status}")
        if search:
            params.append(f"search={search}")
        qs = ("?" + "&".join(params)) if params else ""
        data = self._get(f"/api/workers{qs}")
        if not data:
            return []
        return [_dict_to_worker(d) for d in data]

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        data = self._get(f"/api/workers/{worker_id}")
        if not data:
            return None
        w = _dict_to_worker(data)
        w._documents = data.get("_documents") or {}
        w._meetings = data.get("_meetings") or []
        return w

    def get_documents(self, worker_id: str) -> Dict[str, str]:
        data = self._get(f"/api/workers/{worker_id}/documents")
        return data if isinstance(data, dict) else {}

    def get_meetings(self, worker_id: str) -> List[dict]:
        data = self._get(f"/api/workers/{worker_id}/meetings")
        return data if isinstance(data, list) else []

    def get_pending_count(self) -> int:
        data = self._get("/api/pending/count")
        return data.get("count", 0) if isinstance(data, dict) else 0

    def accept_worker(self, worker_id: str) -> bool:
        resp = self._put(f"/api/workers/{worker_id}/accept")
        return bool(resp)

    def reject_worker(self, worker_id: str, reasons: List[str]) -> bool:
        resp = self._put(f"/api/workers/{worker_id}/reject", {"reasons": reasons})
        return bool(resp)

    def update_worker(self, worker: Worker) -> bool:
        resp = self._put(f"/api/workers/{worker.id}", worker.to_dict())
        return bool(resp)

    def delete_worker(self, worker_id: str) -> bool:
        resp = self._delete(f"/api/workers/{worker_id}")
        return bool(resp)

    def download_file(self, worker_id: str, filename: str) -> Optional[Path]:
        target = self._cache_dir / worker_id / filename
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        url = self.base_url + f"/docs/{worker_id}/{filename}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                target.write_bytes(resp.read())
            return target
        except Exception as e:
            logger.warning("Download %s failed: %s", url, e)
            return None


def _dict_to_worker(d: dict) -> Worker:
    """Construct a Worker from an API dict (no sqlite3.Row needed)."""
    w = Worker(
        id=d.get("id", ""),
        name=d.get("name", ""),
        citizenship=d.get("citizenship", ""),
        gender=d.get("gender", ""),
        position=d.get("position", ""),
        object=d.get("object", ""),
        object_address=d.get("object_address", ""),
        manager=d.get("manager", ""),
        phone_main=d.get("phone_main", ""),
        phone_additional=d.get("phone_additional", ""),
        email=d.get("email", ""),
        date=d.get("date", ""),
        registration=d.get("registration", ""),
        marital_status=d.get("marital_status", ""),
        relatives_json=d.get("relatives_json", "[]"),
        telegram_id=d.get("telegram_id"),
        telegram_username=d.get("telegram_username", ""),
        created_at=d.get("created_at", ""),
        status=d.get("status", "pending"),
        rejection_reasons=d.get("rejection_reasons", "[]"),
    )
    return w


# ── Backward-compatible helper ──

_api_client: Optional[APIClient] = None


def get_db_service() -> APIClient:
    global _api_client
    if _api_client is None:
        from src.config import API_SERVER
        from src.logging_config import diagnostic_log
        diagnostic_log(f"API URL: {API_SERVER}")
        _api_client = APIClient(API_SERVER)
    return _api_client
