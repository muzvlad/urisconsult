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
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.models import Worker

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Ошибка HTTP-ответа API с кодом и текстом сервера."""

    def __init__(self, code: int, message: str = ""):
        super().__init__(f"HTTP {code}: {message}" if message else f"HTTP {code}")
        self.code = code
        self.message = message


def _error_text(e: urllib.error.HTTPError) -> str:
    """Текст ошибки из тела ответа API."""
    try:
        body = e.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        if isinstance(data, dict):
            return str(data.get("error", body))
    except Exception:
        pass
    return getattr(e, "reason", "") or ""


class APIClient:
    """Drop-in replacement for DatabaseService that talks to the API server."""

    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._cache_dir = Path(os.path.expanduser("~")) / ".urisconsult_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def _open(self, req: urllib.request.Request, timeout: int = 30):
        """Открыть запрос, добавив токен доступа, если он задан."""
        if self.token:
            req.add_header("X-API-Token", self.token)
        return urllib.request.urlopen(req, timeout=timeout)

    def _get(self, path: str) -> dict | list | None:
        url = self.base_url + path
        try:
            req = urllib.request.Request(url)
            with self._open(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("GET %s → %s", url, e.code)
            raise APIError(e.code, _error_text(e)) from e
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _put(self, path: str, data: dict = None) -> dict:
        url = self.base_url + path
        body = json.dumps(data or {}).encode()
        try:
            req = urllib.request.Request(url, data=body, method="PUT")
            req.add_header("Content-Type", "application/json")
            with self._open(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("PUT %s → %s", url, e.code)
            raise APIError(e.code, _error_text(e)) from e
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _delete(self, path: str) -> dict:
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, method="DELETE")
            with self._open(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("DELETE %s → %s", url, e.code)
            raise APIError(e.code, _error_text(e)) from e
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    def _post(self, path: str, data: dict) -> dict:
        url = self.base_url + path
        body = json.dumps(data).encode()
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with self._open(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("POST %s → %s", url, e.code)
            raise APIError(e.code, _error_text(e)) from e
        except Exception as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

    # ── Workers ──

    def get_workers(self, status: Optional[str] = None, search: Optional[str] = None,
                    date_from: Optional[str] = None, date_to: Optional[str] = None,
                    archived: str = "0") -> List[Worker]:
        params = {"archived": archived}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        qs = "?" + urllib.parse.urlencode(params)
        data = self._get(f"/api/workers{qs}")
        if not data:
            return []
        return [_dict_to_worker(d) for d in data]

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        try:
            data = self._get(f"/api/workers/{worker_id}")
        except APIError as e:
            if e.code == 404:
                return None
            raise
        if not data:
            return None
        return _dict_to_worker(data)

    def get_documents(self, worker_id: str) -> Dict[str, List[Dict[str, str]]]:
        try:
            data = self._get(f"/api/workers/{worker_id}/documents")
        except APIError as e:
            if e.code == 404:
                return {}
            raise
        return data if isinstance(data, dict) else {}

    def replace_document(self, worker_id: str, doc_type: str,
                         old_filename: str, file_path: Path) -> bool:
        """Перезалить документ: заменить файл с тем же именем."""
        url = self.base_url + f"/api/workers/{worker_id}/documents"
        try:
            boundary = "----urisconsult" + str(id(file_path))
            parts = []
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"doc_type\"\r\n\r\n{doc_type}\r\n")
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"old_filename\"\r\n\r\n{old_filename}\r\n")
            filename = file_path.name
            parts.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n"
            )
            head = "".join(parts).encode()
            tail = f"\r\n--{boundary}--\r\n".encode()
            body = head + file_path.read_bytes() + tail

            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            with self._open(req, 60) as resp:
                result = json.loads(resp.read().decode())
            if result.get("ok"):
                self._drop_cache(worker_id, old_filename)
            return bool(result.get("ok"))
        except urllib.error.HTTPError as e:
            logger.warning("replace_document %s failed: %s", url, e.code)
            raise APIError(e.code, _error_text(e)) from e
        except APIError:
            raise
        except Exception as e:
            logger.warning("replace_document %s failed: %s", url, e)
            return False

    def _drop_cache(self, worker_id: str, filename: str) -> None:
        """Удалить кэшированный файл — после перезаливки содержимое изменилось."""
        if not filename:
            return
        try:
            (self._cache_dir / worker_id / filename).unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Не удалось удалить кэш %s/%s: %s", worker_id, filename, e)

    def get_meetings(self, worker_id: str) -> List[dict]:
        try:
            data = self._get(f"/api/workers/{worker_id}/meetings")
        except APIError as e:
            if e.code == 404:
                return []
            raise
        return data if isinstance(data, list) else []

    def add_meeting(self, worker_id: str, date: str, note: str) -> bool:
        resp = self._post(f"/api/workers/{worker_id}/meetings", {"date": date, "note": note})
        return bool(resp)

    def get_notes(self, worker_id: str) -> List[dict]:
        try:
            data = self._get(f"/api/workers/{worker_id}/notes")
        except APIError as e:
            if e.code == 404:
                return []
            raise
        return data if isinstance(data, list) else []

    def add_note(self, worker_id: str, text: str) -> bool:
        return bool(self._post(f"/api/workers/{worker_id}/notes", {"text": text}))

    def update_note(self, worker_id: str, note_id: int, text: str) -> bool:
        return bool(self._put(f"/api/workers/{worker_id}/notes/{note_id}", {"text": text}))

    def delete_note(self, worker_id: str, note_id: int) -> bool:
        return bool(self._delete(f"/api/workers/{worker_id}/notes/{note_id}"))

    def set_legal_entity(self, worker_id: str, value: str) -> bool:
        return bool(self._put(f"/api/workers/{worker_id}/legal-entity",
                              {"legal_entity": value}))

    def set_hr_status(self, worker_id: str, status: str, date_value: str = "") -> bool:
        return bool(self._put(f"/api/workers/{worker_id}/hr-status",
                              {"hr_status": status, "hr_status_date": date_value}))

    def set_documents_signed(self, worker_id: str, value: str) -> bool:
        return bool(self._put(f"/api/workers/{worker_id}/documents-signed",
                              {"documents_signed": value}))

    def archive_worker(self, worker_id: str) -> bool:
        return bool(self._post(f"/api/workers/{worker_id}/archive", {}))

    def unarchive_worker(self, worker_id: str) -> bool:
        return bool(self._post(f"/api/workers/{worker_id}/unarchive", {}))

    def get_pending_count(self) -> int:
        try:
            data = self._get("/api/pending/count")
        except APIError as e:
            if e.code == 404:
                return 0
            raise
        return data.get("count", 0) if isinstance(data, dict) else 0

    def accept_worker(self, worker_id: str) -> bool:
        resp = self._put(f"/api/workers/{worker_id}/accept")
        return bool(resp)

    def reject_worker(self, worker_id: str, reasons: List[Dict[str, str]]) -> bool:
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
            with self._open(req) as resp:
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
        customer=d.get("customer", ""),
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
        updated_at=d.get("updated_at", ""),
        status=d.get("status", "pending"),
        rejection_reasons=d.get("rejection_reasons", "[]"),
        legal_entity=d.get("legal_entity", ""),
        hr_status=d.get("hr_status", "not_processed") or "not_processed",
        hr_status_date=d.get("hr_status_date", ""),
        documents_signed=d.get("documents_signed", "0"),
        archived_at=d.get("archived_at", ""),
    )
    return w


# ── Backward-compatible helper ──

_api_client: Optional[APIClient] = None


def get_db_service() -> APIClient:
    global _api_client
    if _api_client is None:
        from src.config import API_SERVER, API_TOKEN
        from src.logging_config import diagnostic_log
        diagnostic_log(f"API URL: {API_SERVER}")
        _api_client = APIClient(API_SERVER, API_TOKEN)
    return _api_client
