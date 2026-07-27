"""
Конфигурация приложения: пути, настройки, константы.
Поддерживает работу и в режиме разработки, и в собранном exe (PyInstaller).
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from functools import lru_cache


@dataclass(frozen=True)
class AppPaths:
    """Все пути приложения."""
    # Корень проекта
    project_root: Path
    # БД
    db_path: Path
    # Папка с документами
    docs_dir: Path
    # Папка бота (для конфигов)
    bot_dir: Path

    @property
    def env_path(self) -> Path:
        return self.bot_dir / ".env"


@dataclass(frozen=True)
class AppConfig:
    """Настройки приложения."""
    # Размеры окна
    window_width: int = 1300
    window_height: int = 850
    min_window_width: int = 1000
    min_window_height: int = 700

    # Цвета
    bg_color: str = "#f0f0f0"
    header_bg: str = "#2c3e50"
    header_fg: str = "white"
    accent_blue: str = "#3498db"
    accent_green: str = "#27ae60"
    accent_red: str = "#e74c3c"
    accent_orange: str = "#e67e22"
    accent_gray: str = "#95a5a6"
    warning_bg: str = "#ffeaa7"

    # Размеры миниатюр
    thumbnail_size: Tuple[int, int] = (200, 200)
    small_thumbnail_size: Tuple[int, int] = (120, 120)

    # PDF экспорт
    pdf_photo_size: Tuple[int, int] = (80, 80)
    pdf_doc_size: Tuple[int, int] = (60, 60)

    # Таймауты
    telegram_timeout: int = 10
    db_timeout: float = 30.0

    # Поддерживаемые расширения изображений
    image_extensions: List[str] = field(default_factory=lambda: [
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"
    ])

    # Статусы
    status_pending: str = "pending"
    status_accepted: str = "accepted"
    status_rejected: str = "rejected"

    # Цвета статусов
    status_colors: Dict[str, str] = field(default_factory=lambda: {
        "pending": "#f39c12",
        "accepted": "#27ae60",
        "rejected": "#e74c3c",
    })

    # Иконки статусов
    status_icons: Dict[str, str] = field(default_factory=lambda: {
        "pending": "⏳",
        "accepted": "✅",
        "rejected": "❌",
    })

    # Заголовок приложения
    app_title: str = "URIS Consult — Просмотр карточек"


# ─── Определение путей ───

def _get_base_path() -> Path:
    """
    Получить базовый путь проекта.
    Работает и в dev режиме, и в PyInstaller (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        # В собранном exe: sys._MEIPASS - временная папка распаковки
        # Нам нужен каталог, где лежит exe (рядом с ним данные)
        return Path(sys.executable).parent
    # В dev режиме: корень проекта (на 2 уровня выше от этого файла)
    return Path(__file__).parent.parent.parent


def _get_project_root() -> Path:
    """Найти корень проекта по маркерам (.git, bot/, UI/)."""
    base = _get_base_path()
    # Ищем вверх по дереву
    for parent in [base] + list(base.parents):
        if (parent / "bot").exists() and (parent / "UI").exists():
            return parent
        if (parent / ".git").exists():
            return parent
    return base


# ─── API сервер ───
def _get_api_server() -> str:
    """Прочитать адрес API сервера: env var > .env файл > hardcoded."""
    # 1. Переменная окружения (run.bat, docker и т.д.)
    env_val = os.environ.get("API_SERVER", "").strip()
    if env_val:
        return env_val
    # 2. .env файл
    base = _get_base_path()
    env_candidates = [
        base / "bot" / ".env",
        base / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("API_SERVER="):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass
    # 3. Hardcoded fallback (сервер бота)
    return "http://144.76.70.246:8080"

API_SERVER = _get_api_server()


def _log_config(msg):
    """Лог конфигурации в файл."""
    import sys
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        paths = [
            os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'ui_error.log'),
            os.path.join(os.path.expanduser('~'), 'ui_error.log'),
        ]
        for p in paths:
            try:
                with open(p, 'a', encoding='utf-8') as f:
                    f.write(f"[{ts}] {msg}\n")
            except Exception:
                continue
            break
    except Exception:
        pass

_log_config(f"API_SERVER={API_SERVER}")


@lru_cache(maxsize=1)
def get_paths() -> AppPaths:
    """Получить все пути приложения (кэшируется)."""
    root = _get_project_root()
    _log_config(f"Локальный режим: {root}")
    return AppPaths(
        project_root=root,
        db_path=root / "bot" / "Users" / "users.db",
        docs_dir=root / "bot" / "Users" / "docs",
        bot_dir=root / "bot",
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Получить конфигурацию (кэшируется)."""
    return AppConfig()


def get_bot_token() -> Optional[str]:
    """Прочитать токен бота из .env файла."""
    paths = get_paths()
    if not paths.env_path.exists():
        return None
    try:
        with open(paths.env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def get_document_config() -> Tuple[Dict, Dict, Dict]:
    """
    Получить конфиг документов из бота.
    Возвращает (DOC_FLOWS, DOC_LABELS, DOC_PREFIXES).
    """
    paths = get_paths()
    bot_config_dir = paths.bot_dir / "config"

    # Сохраняем и восстанавливаем sys.path чтобы не засорять
    old_path = sys.path.copy()
    try:
        if str(bot_config_dir.parent) not in sys.path:
            sys.path.insert(0, str(bot_config_dir.parent))
        from config.documents import DOC_FLOWS, DOC_LABELS, DOC_PREFIXES
        return DOC_FLOWS, DOC_LABELS, DOC_PREFIXES
    except ImportError:
        return {}, {}, {}
    finally:
        sys.path = old_path


# ─── Константы БД (импортируются из общего модуля) ───
import sys as _sys

def _import_shared():
    """Импортировать shared модуль с поиском по нескольким путям."""
    # Вариант 1: уже есть в sys.path (dev режим)
    try:
        import shared
        return shared
    except ImportError:
        pass

    # Вариант 2: PyInstaller — ищем в _MEIPASS
    if getattr(_sys, "frozen", False):
        meipass = Path(_sys._MEIPASS)
        for name in ["shared", "Shared"]:
            p = meipass / name
            if p.exists() and str(p) not in _sys.path:
                _sys.path.insert(0, str(p))
            try:
                import shared
                return shared
            except ImportError:
                pass

    # Вариант 3: корень проекта
    root = Path(__file__).parent.parent.parent
    for name in ["shared", "Shared"]:
        p = root / name
        if p.exists() and str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
    try:
        import shared
        return shared
    except ImportError:
        raise ImportError("Cannot find 'shared' module. Checked: sys.path, _MEIPASS, project root")

_shared = _import_shared()

WORKERS_TABLE = _shared.WORKERS_TABLE
WORKER_DOCUMENTS_TABLE = _shared.WORKER_DOCUMENTS_TABLE
WORKER_MEETINGS_TABLE = _shared.WORKER_MEETINGS_TABLE
WORKER_SCHEMA = _shared.WORKER_SCHEMA
WORKER_DOCUMENTS_SCHEMA = _shared.WORKER_DOCUMENTS_SCHEMA
WORKER_MEETINGS_SCHEMA = _shared.WORKER_MEETINGS_SCHEMA
MIGRATIONS = _shared.MIGRATIONS


# ─── Вспомогательные функции ───

def center_window(window: "tk.Tk | tk.Toplevel", width: int, height: int) -> None:
    """Центрировать окно на экране."""
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def format_phone(phone: str) -> str:
    """Форматировать номер телефона для отображения."""
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 11 and digits[0] == '7':
        # Российский номер +7
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    elif len(digits) == 10 and digits[0] == '9':
        # Российный номер без кода страны
        return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    elif len(digits) > 10:
        # Международный номер — форматируем с пробелами для читаемости
        formatted = ""
        for i, d in enumerate(digits):
            if i > 0 and i % 3 == 0:
                formatted += " "
            formatted += d
        return f"+{formatted}"
    return phone


def truncate_text(text: str, max_len: int = 60) -> str:
    """Обрезать текст с многоточием."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ─── Экспорт для обратной совместимости ───

# Пути
PROJECT_ROOT = get_paths().project_root
DB_PATH = get_paths().db_path
DOCS_DIR = get_paths().docs_dir
BOT_DIR = get_paths().bot_dir

# Конфиг
CONFIG = get_config()