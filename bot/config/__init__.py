"""
Конфигурация бота — пакет.

Все импорты из `from config import X` продолжают работать.
Новые импорты: `from config.documents import DOC_FLOWS, get_doc_flow, ...`
"""
import logging
import os
import sys
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

# Чтобы `import shared` работал при запуске из bot/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(BASE_DIR, '.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN")
NETWORK_SERVER = os.getenv("NETWORK_SERVER", "")

# Порт HTTP-API (Flask). Один на весь проект: UI ходит только на него.
API_PORT = int(os.getenv("API_PORT", "56755"))

# Токен доступа к API. Пусто — API работает без авторизации (как раньше).
API_TOKEN = os.getenv("API_TOKEN", "")

# Пути к папкам — приоритет сетевому серверу
try:
    if NETWORK_SERVER and os.path.isdir(NETWORK_SERVER):
        USERS_DIR = os.path.join(NETWORK_SERVER, "bot", "Users")
        DB_PATH = os.path.join(USERS_DIR, "users.db")
        DOCS_DIR = os.path.join(USERS_DIR, "docs")
    else:
        raise OSError("Network server not available")
except (OSError, PermissionError):
    if NETWORK_SERVER:
        logging.getLogger(__name__).warning(
            "Сетевой сервер %s недоступен — используется локальная БД %s",
            NETWORK_SERVER, os.path.join(BASE_DIR, "Users"))
    USERS_DIR = os.path.join(BASE_DIR, "Users")
    DB_PATH = os.path.join(USERS_DIR, "users.db")
    DOCS_DIR = os.path.join(USERS_DIR, "docs")


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
