"""
Модуль логирования с ротацией файлов и консольным выводом.
"""
from __future__ import annotations
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from src.config import get_paths


# Глобальный логгер
_logger: Optional[logging.Logger] = None


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Настроить логирование приложения.

    Args:
        level: Уровень логирования
        log_to_file: Записывать в файл
        log_to_console: Выводить в консоль
        max_bytes: Максимальный размер файла лога
        backup_count: Количество бэкапов

    Returns:
        Настроенный логгер
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger("urisconsult")
    logger.setLevel(level)
    logger.propagate = False

    # Очистка существующих обработчиков
    logger.handlers.clear()

# Форматтер
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный обработчик — только ошибки
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Файловый обработчик с ротацией
    if log_to_file:
        try:
            paths = get_paths()
            log_dir = paths.project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "app.log"

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Если не удалось создать файловый логгер, продолжаем с консольным
            if log_to_console:
                logger.warning(f"Could not setup file logging: {e}")

    _logger = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Получить логгер.

    Args:
        name: Имя логгера (добавляется к 'urisconsult.')

    Returns:
        Логгер
    """
    if _logger is None:
        setup_logging()

    if name:
        return logging.getLogger(f"urisconsult.{name}")
    return _logger


# Удобные функции для быстрого логирования
def log_info(message: str, *args, **kwargs) -> None:
    get_logger().info(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs) -> None:
    get_logger().warning(message, *args, **kwargs)


def log_error(message: str, *args, exc_info: bool = False, **kwargs) -> None:
    get_logger().error(message, *args, exc_info=exc_info, **kwargs)


def log_exception(message: str, *args, **kwargs) -> None:
    get_logger().exception(message, *args, **kwargs)


def log_debug(message: str, *args, **kwargs) -> None:
    get_logger().debug(message, *args, **kwargs)


def diagnostic_log(msg: str) -> None:
    """Лог в файл для диагностики (до инициализации основного логирования)."""
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