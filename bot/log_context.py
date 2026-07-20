"""
Фильтры для логирования.

Добавляет contextvars для worker_id и user_id в логи.
"""
import contextvars

# Context variables для логирования
worker_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'worker_id', default=None
)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    'user_id', default=None
)


class WorkerContextFilter:
    """Фильтр, добавляющий worker_id и user_id в логи."""

    def filter(self, record):
        record.worker_id = worker_id_var.get() or '-'
        record.user_id = user_id_var.get() or '-'
        return True


def setup_logging_filters():
    """Установить фильтры логирования (вызывается при старте бота)."""
    import logging
    worker_filter = WorkerContextFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(worker_filter)
    # Также для корневого логгера
    logging.getLogger().addFilter(worker_filter)
