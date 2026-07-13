"""
Конфигурация бота — пакет.

Все импорты из `from config import X` продолжают работать.
Новые импорты: `from config.documents import DOC_FLOWS, get_doc_flow, ...`
"""
import os
from dotenv import load_dotenv

from config.documents import (  # noqa: F401 — re-export
    DOC_FLOWS, DOC_PREFIXES, DOC_LABELS, FIELD_LABELS, DOC_PROMPTS,
    CITIZENSHIP_DOC_KEYS, get_doc_flow, get_next_doc, get_doc_by_key,
)

# ─── Базовые пути ─────────────────────────────────────────────────────
# __file__ = bot/config/__init__.py  →  bot/config/  →  bot/
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CONFIG_DIR)  # bot/
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # корень проекта

load_dotenv(os.path.join(BASE_DIR, '.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Пути к папкам
USERS_DIR = os.path.join(BASE_DIR, "Users")
DB_PATH = os.path.join(USERS_DIR, "users.db")
DOCS_DIR = os.path.join(PROJECT_ROOT, "users", "docs")


def ensure_dirs():
    """Создать необходимые папки (вызывается при старте бота)."""
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

# Форматы файлов
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.pdf']

# Максимальный размер файла (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# MIME-типы для валидации
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp',
    'application/pdf',
}
