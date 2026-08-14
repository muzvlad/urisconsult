"""Flask API server for URIS Consult application."""
import os
import sys
import shutil
import asyncio
import tempfile
import mimetypes
import logging
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, DOCS_DIR
from services import db

app = Flask(__name__)

_logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

MIME_OVERRIDES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif',
    '.bmp': 'image/bmp', '.pdf': 'application/pdf',
}


def run_async(coro):
    return asyncio.run(coro)


# ─── Workers ───────────────────────────────────────────────────────────

@app.route('/api/workers', methods=['GET'])
def list_workers():
    status = request.args.get('status')
    search = request.args.get('search')
    try:
        if search:
            workers = run_async(db.search_workers(search))
        elif status:
            workers = run_async(db.get_workers_by_status(status))
        else:
            workers = run_async(db.get_all_workers())
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
        from datetime import datetime
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

            is_valid, err = FileSaver.validate_file(tmp_path)
            if not is_valid:
                return jsonify({"error": err}), 400

            if old_filename:
                # Перезаливка: перезаписываем файл под старым именем
                worker_dir = os.path.join(DOCS_DIR, worker_id)
                os.makedirs(worker_dir, exist_ok=True)
                new_path = os.path.join(worker_dir, os.path.basename(old_filename))
                shutil.copy2(tmp_path, new_path)
                run_async(db.replace_document(worker_id, doc_type, old_filename))
            else:
                FileSaver.save_document(tmp_path, worker_id, doc_type)

            # Обновляем дату редактирования анкеты
            worker = run_async(db.get_worker(worker_id))
            if worker:
                run_async(db.save_worker({**worker, 'updated_at': datetime.now().isoformat()}))

            return jsonify({"ok": True})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        _logger.error("upload_document(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    try:
        from datetime import datetime
        data = request.get_json(force=True)
        data['id'] = worker_id
        data['updated_at'] = datetime.now().isoformat()
        run_async(db.save_worker(data))
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("update_worker(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    try:
        async def _delete():
            async with db._get_conn() as conn:
                await conn.execute("DELETE FROM worker_documents WHERE worker_id = ?", (worker_id,))
                await conn.execute("DELETE FROM worker_meetings WHERE worker_id = ?", (worker_id,))
                await conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
                await conn.commit()

        run_async(_delete())

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
        async def _get_meetings():
            async with db._get_conn() as conn:
                cursor = await conn.execute(
                    "SELECT id, date, note, created_at FROM worker_meetings WHERE worker_id = ? ORDER BY id",
                    (worker_id,),
                )
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

        meetings = run_async(_get_meetings())
        return jsonify(meetings)
    except Exception as e:
        _logger.error("list_meetings(%s) error: %s", worker_id, e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/workers/<worker_id>/meetings', methods=['POST'])
def add_meeting(worker_id):
    try:
        data = request.get_json(force=True)

        async def _add():
            async with db._get_conn() as conn:
                await conn.execute(
                    "INSERT INTO worker_meetings (worker_id, date, note) VALUES (?, ?, ?)",
                    (worker_id, data.get('date', ''), data.get('note', '')),
                )
                await conn.commit()

        run_async(_add())
        return jsonify({"ok": True})
    except Exception as e:
        _logger.error("add_meeting(%s) error: %s", worker_id, e)
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
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
