"""Flask API server for URIS Consult application."""
import os
import sys
import shutil
import asyncio
import mimetypes
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, DOCS_DIR
from services import db

app = Flask(__name__)

import logging
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
            workers = run_async(db.get_all_workers())
            workers = [w for w in workers if w.get('status') == status]
        else:
            workers = run_async(db.get_all_workers())
        return jsonify(workers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/workers/<worker_id>', methods=['GET'])
def get_worker(worker_id):
    try:
        worker = run_async(db.get_worker(worker_id))
        if not worker:
            return jsonify({"error": "Worker not found"}), 404
        return jsonify(worker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/workers/<worker_id>/documents', methods=['GET'])
def get_worker_documents(worker_id):
    try:
        docs = run_async(db.get_worker_documents(worker_id))
        return jsonify(docs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/workers/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    try:
        data = request.get_json(force=True)
        data['id'] = worker_id
        run_async(db.save_worker(data))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/workers/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    try:
        import aiosqlite

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
        return jsonify({"error": str(e)}), 500


# ─── Status ────────────────────────────────────────────────────────────

@app.route('/api/workers/<worker_id>/accept', methods=['PUT'])
def accept_worker(worker_id):
    try:
        run_async(db.accept_worker(worker_id))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/workers/<worker_id>/reject', methods=['PUT'])
def reject_worker(worker_id):
    try:
        data = request.get_json(force=True)
        reasons = data.get('reasons', [])
        run_async(db.reject_worker(worker_id, reasons))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Pending count ─────────────────────────────────────────────────────

@app.route('/api/pending/count', methods=['GET'])
def pending_count():
    try:
        count = run_async(db.get_pending_count())
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


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
    app.run(host='0.0.0.0', port=8080, debug=False)
