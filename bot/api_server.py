"""Flask API server for URIS Consult application."""
import os
import sys
import re
import shutil
import asyncio
import hmac
import tempfile
import mimetypes
import logging
import threading
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, DOCS_DIR, API_PORT, API_TOKEN, MAX_FILE_SIZE
from services import db

app = Flask(__name__)

# Тело запроса ограничено: файл до 20 МБ + 1 МБ на multipart-обвязку
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE + 1024 * 1024

_logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

MIME_OVERRIDES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif',
    '.bmp': 'image/bmp', '.pdf': 'application/pdf',
}

# ID анкеты и имя файла — только буквы, цифры, дефис и подчёркивание.
# Без этой проверки worker_id='..' уводит пути за пределы DOCS_DIR.
SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
SAFE_FILENAME_RE = re.compile(r'^[A-Za-z0-9_.-]{1,128}$')

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


@app.before_request
def _guard_request():
    """Авторизация и проверка параметров пути до обработчика."""
    if API_TOKEN:
        token = request.headers.get('X-API-Token', '')
        if not token or not hmac.compare_digest(token.encode(), API_TOKEN.encode()):
            return jsonify({"error": "Unauthorized"}), 401

    args = request.view_args or {}
    worker_id = args.get('worker_id')
    if worker_id is not None and not SAFE_ID_RE.match(worker_id):
        return jsonify({"error": "Invalid worker_id"}), 400

    filename = args.get('filename')
    if filename is not None and (not SAFE_FILENAME_RE.match(filename)
                                 or '..' in filename):
        return jsonify({"error": "Invalid filename"}), 400


def _ensure_loop():
    """Гарантировать наличие одного event loop в фоновом потоке."""
    global _loop
    if _loop is None:
        with _loop_lock:
            if _loop is None:
                _loop = asyncio.new_event_loop()
                t = threading.Thread(target=_loop.run_forever, daemon=True, name="api-event-loop")
                t.start()


def run_async(coro):
    """Выполнить корутину на общем event loop (без asyncio.run на каждый запрос)."""
    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=30)


def _valid_iso_date(value: str) -> bool:
    """Проверить дату в формате YYYY-MM-DD."""
    from datetime import datetime
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return False
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def _valid_meeting_date(value: str) -> bool:
    """Проверить дату встречи: дд.мм.гггг или дд.мм.гггг чч:мм."""
    from datetime import datetime
    if not isinstance(value, str):
        return False
    for fmt, pattern in (
        ('%d.%m.%Y %H:%M', r'\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}'),
        ('%d.%m.%Y', r'\d{2}\.\d{2}\.\d{4}'),
    ):
        if re.fullmatch(pattern, value):
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                return False
    return False


def _valid_hr_date(value: str) -> bool:
    """Проверить HR-дату: дд.мм.гггг или YYYY-MM-DD."""
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


# ─── Workers ───────────────────────────────────────────────────────────

@app.route('/api/workers', methods=['GET'])
def list_workers():
    status = request.args.get('status')
    search = request.args.get('search')
    archived = request.args.get('archived', '0')
    date_from = request.args.get('date_from') or None
    date_to = request.args.get('date_to') or None

    if archived not in ('0', '1', 'all'):
        return jsonify({"error": "Invalid archived"}), 400
    if date_from and not _valid_iso_date(date_from):
        return jsonify({"error": "Invalid date_from"}), 400
    if date_to and not _valid_iso_date(date_to):
        return jsonify({"error": "Invalid date_to"}), 400

    try:
        if search:
            workers = run_async(db.search_workers(search, archived, date_from, date_to))
        elif status:
            workers = run_async(db.get_workers_by_status(status, archived, date_from, date_to))
        else:
            workers = run_async(db.get_all_workers(archived, date_from, date_to))
        return jsonify(workers)
    except Exception as e:
        logging.getLogger(__name__).error("list_workers error: %s", e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>', methods=['GET'])
def get_worker(worker_id):
    try:
        worker = run_async(db.get_worker(worker_id))
        if not worker:
            return jsonify({"error": "Worker not found"}), 404
        return jsonify(worker)
    except Exception as e:
        _logger.error("get_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/documents', methods=['GET'])
def get_worker_documents(worker_id):
    try:
        docs = run_async(db.get_worker_documents(worker_id))
        return jsonify(docs)
    except Exception as e:
        _logger.error("get_worker_documents(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/documents', methods=['POST'])
def upload_document(worker_id):
    """Загрузка/перезаливка документа из UI. multipart: doc_type, file, old_filename(optional)."""
    try:
        from services.file_saver import FileSaver

        doc_type = request.form.get('doc_type', '')
        old_filename = request.form.get('old_filename', '') or None
        file_storage = request.files.get('file')
        if not file_storage:
            return jsonify({"error": "No file"}), 400

        tmp_dir = tempfile.mkdtemp(prefix='ui_doc_')
        try:
            src_ext = os.path.splitext(file_storage.filename or '')[-1].lower()
            tmp_path = os.path.join(tmp_dir, 'upload' + (src_ext or '.jpg'))
            file_storage.save(tmp_path)

            is_valid, err = FileSaver.validate_file(tmp_path, os.path.getsize(tmp_path))
            if not is_valid:
                return jsonify({"error": err}), 400

            is_valid, err = FileSaver.check_magic(tmp_path)
            if not is_valid:
                return jsonify({"error": err}), 400

            if old_filename:
                # Перезаливка: файл перезаписывается под старым именем,
                # запись в worker_documents остаётся, обновляется created_at
                worker_dir = os.path.join(DOCS_DIR, worker_id)
                os.makedirs(worker_dir, exist_ok=True)
                new_path = os.path.join(worker_dir, os.path.basename(old_filename))
                shutil.copy2(tmp_path, new_path)
                run_async(db.replace_document(worker_id, doc_type, old_filename))
            else:
                filename = FileSaver.save_document(tmp_path, worker_id, doc_type)
                # Без записи в БД документ не виден в карточке
                run_async(db.add_document(worker_id, doc_type, filename))

            # Обновляем дату редактирования анкеты
            worker = run_async(db.get_worker(worker_id))
            if worker:
                run_async(db.save_worker({**worker, 'updated_at': db.now_msk().isoformat()}))

            return jsonify({"ok": True})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        _logger.error("upload_document(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    try:
        data = request.get_json(force=True)
        data['id'] = worker_id
        data['updated_at'] = db.now_msk().isoformat()
        run_async(db.save_worker(data))
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("update_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    try:
        run_async(db.delete_worker(worker_id))

        worker_dir = os.path.join(DOCS_DIR, worker_id)
        if os.path.isdir(worker_dir):
            shutil.rmtree(worker_dir, ignore_errors=True)

        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("delete_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


# ─── Status ────────────────────────────────────────────────────────────

@app.route('/api/workers/<worker_id>/accept', methods=['PUT'])
def accept_worker(worker_id):
    try:
        run_async(db.accept_worker(worker_id))
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("accept_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/reject', methods=['PUT'])
def reject_worker(worker_id):
    try:
        data = request.get_json(force=True)
        reasons = data.get('reasons', [])
        run_async(db.reject_worker(worker_id, reasons))
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("reject_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/resubmit', methods=['PUT'])
def resubmit_worker(worker_id):
    try:
        run_async(db.resubmit_worker(worker_id))
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("resubmit_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/archive', methods=['POST'])
def archive_worker(worker_id):
    try:
        ok = run_async(db.archive_worker(worker_id))
        return jsonify({"ok": ok}), (200 if ok else 404)
    except Exception as e:
        _logger.error("archive_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/unarchive', methods=['POST'])
def unarchive_worker(worker_id):
    try:
        ok = run_async(db.unarchive_worker(worker_id))
        return jsonify({"ok": ok}), (200 if ok else 404)
    except Exception as e:
        _logger.error("unarchive_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/legal-entity', methods=['PUT'])
def set_legal_entity(worker_id):
    try:
        data = request.get_json(force=True)
        ok = run_async(db.set_legal_entity(worker_id, str(data.get('legal_entity', ''))))
        return jsonify({"ok": ok}), (200 if ok else 404)
    except Exception as e:
        _logger.error("set_legal_entity(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/hr-status', methods=['PUT'])
def set_hr_status(worker_id):
    """Изменить HR-статус (внутренний кадровый процесс).

    Доступные статусы: not_processed, docs_pending, employed, rejected,
    fired, notify (Уведомить), mvd_check (На проверке МВД).
    Дата (ДД.ММ.ГГГГ) активна для любого статуса, но не обязательна.
    Меняется только из UI; клиент не видит этих полей.
    """
    try:
        data = request.get_json(force=True)
        status = data.get('hr_status', '')
        date_value = data.get('hr_status_date')
        if isinstance(date_value, str):
            date_value = date_value.strip() or None
        if status not in db.HR_STATUSES:
            return jsonify({"error": "Invalid hr_status"}), 400
        if status in ('employed', 'fired') and not date_value:
            return jsonify({"error": "Date required for this status"}), 400
        if date_value is not None and not _valid_hr_date(date_value):
            return jsonify({"error": "Invalid hr_status_date"}), 400
        ok = run_async(db.set_hr_status(worker_id, status, date_value))
        return jsonify({"ok": ok}), (200 if ok else 400)
    except Exception as e:
        _logger.error("set_hr_status(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/documents-signed', methods=['PUT'])
def set_documents_signed(worker_id):
    """Внутренний HR-флаг «Документы подписаны» — меняется только из UI."""
    try:
        data = request.get_json(force=True)
        value = str(data.get('documents_signed', ''))
        ok = run_async(db.set_documents_signed(worker_id, value))
        return jsonify({"ok": ok}), (200 if ok else 404)
    except Exception as e:
        _logger.error("set_documents_signed(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


# ─── Pending count ─────────────────────────────────────────────────────

@app.route('/api/pending/count', methods=['GET'])
def pending_count():
    try:
        count = run_async(db.get_pending_count())
        return jsonify({"count": count})
    except Exception as e:
        _logger.error("pending_count error: %s", e)
        return jsonify({"error": "Internal error"}), 500


# ─── Meetings ──────────────────────────────────────────────────────────

@app.route('/api/workers/<worker_id>/meetings', methods=['GET'])
def list_meetings(worker_id):
    try:
        meetings = run_async(db.get_meetings(worker_id))
        return jsonify(meetings)
    except Exception as e:
        _logger.error("list_meetings(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/meetings', methods=['POST'])
def add_meeting(worker_id):
    try:
        data = request.get_json(force=True)
        date_value = str(data.get('date', '')).strip()
        note = str(data.get('note', '')).strip()
        if not date_value or not _valid_meeting_date(date_value):
            return jsonify({"error": "Invalid meeting date"}), 400
        meeting_id = run_async(db.add_meeting(worker_id, date_value, note))
        return jsonify({"ok": True, "id": meeting_id})
    except Exception as e:
        _logger.error("add_meeting(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


# ─── Notes ─────────────────────────────────────────────────────────────

@app.route('/api/workers/<worker_id>/notes', methods=['GET'])
def list_notes(worker_id):
    try:
        return jsonify(run_async(db.get_worker_notes(worker_id)))
    except Exception as e:
        _logger.error("list_notes(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/notes', methods=['POST'])
def add_note(worker_id):
    try:
        data = request.get_json(force=True)
        note_id = run_async(db.add_worker_note(worker_id, str(data.get('text', ''))))
        if note_id is None:
            return jsonify({"error": "Empty note"}), 400
        return jsonify({"ok": True, "id": note_id})
    except Exception as e:
        _logger.error("add_note(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/notes/<int:note_id>', methods=['PUT'])
def update_note(worker_id, note_id):
    try:
        data = request.get_json(force=True)
        ok = run_async(db.update_worker_note(note_id, str(data.get('text', '')), worker_id))
        return jsonify({"ok": ok}), (200 if ok else 400)
    except Exception as e:
        _logger.error("update_note(%s) error: %s", note_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/notes/<int:note_id>', methods=['DELETE'])
def delete_note(worker_id, note_id):
    try:
        ok = run_async(db.delete_worker_note(note_id, worker_id))
        return jsonify({"ok": ok}), (200 if ok else 404)
    except Exception as e:
        _logger.error("delete_note(%s) error: %s", note_id, e)
        return jsonify({"error": "Internal error"}), 500


# ─── File serving ──────────────────────────────────────────────────────

@app.route('/docs/<worker_id>/<filename>')
def serve_doc(worker_id, filename):
    worker_dir = os.path.join(DOCS_DIR, worker_id)
    if not os.path.isdir(worker_dir):
        return jsonify({"error": "Worker docs not found"}), 404
    filepath = os.path.join(worker_dir, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    ext = os.path.splitext(filename)[1].lower()
    mime = MIME_OVERRIDES.get(ext) or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return send_from_directory(worker_dir, filename, mimetype=mime)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=API_PORT, debug=False, threaded=True)
