"""
Сервис для сохранения файлов документов.

Включает валидацию MIME-типа и размера файла.
"""
import os
import logging
from config import DOCS_DIR, MAX_FILE_SIZE, ALLOWED_MIME_TYPES
from config.documents import DOC_PREFIXES

logger = logging.getLogger(__name__)


class FileSaver:
    """Класс для сохранения файлов в папку docs."""

    @staticmethod
    def validate_file(file_path: str, file_size: int = 0) -> tuple[bool, str]:
        """
        Валидация файла по размеру и MIME-типу.

        Args:
            file_path: путь к файлу
            file_size: размер файла в байтах (если известен)

        Returns:
            (is_valid, error_message)
        """
        # Проверка размера
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f"Файл слишком большой ({size_mb:.1f}MB). Максимум: {max_mb}MB"

        # Проверка расширения
        ext = os.path.splitext(file_path)[1].lower()
        allowed_by_ext = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.bmp': 'image/bmp',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
        }

        if ext not in allowed_by_ext:
            return False, f"Недопустимый формат: {ext}. Разрешены: {', '.join(allowed_by_ext.keys())}"

        mime = allowed_by_ext[ext]
        if mime not in ALLOWED_MIME_TYPES:
            return False, f"Недопустимый MIME-тип: {mime}"

        return True, ""

    @staticmethod
    def save_document(temp_path: str, worker_id: str, doc_type: str) -> str:
        """
        Сохранить документ в папку docs с правильным именем.

        Args:
            temp_path: путь к временному файлу
            worker_id: ID работника
            doc_type: тип документа (ключ из DOC_FLOWS)

        Returns:
            Имя сохраненного файла

        Raises:
            FileNotFoundError: если временный файл не найден
            ValueError: если файл не прошёл валидацию
        """
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Временный файл не найден: {temp_path}")

        # Валидация
        file_size = os.path.getsize(temp_path)
        is_valid, error_msg = FileSaver.validate_file(temp_path, file_size)
        if not is_valid:
            raise ValueError(error_msg)

        prefix = DOC_PREFIXES.get(doc_type, 'doc')
        ext = os.path.splitext(temp_path)[1].lower()

        new_filename = f"{prefix}_{worker_id}{ext}"
        new_path = os.path.join(DOCS_DIR, new_filename)

        os.replace(temp_path, new_path)
        logger.debug("Файл сохранён: %s -> %s (%d bytes)", temp_path, new_filename, file_size)
        return new_filename

    @staticmethod
    def cleanup_temp_files(file_paths: list):
        """Очистить временные файлы."""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug("Удалён временный файл: %s", file_path)
            except OSError as e:
                logger.warning("Ошибка при удалении %s: %s", file_path, e)
