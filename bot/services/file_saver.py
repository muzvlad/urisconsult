"""
Сервис для сохранения файлов документов.

Включает валидацию MIME-типа и размера файла.
"""
import os
import shutil
import logging
from config import DOCS_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS
from config.documents import DOC_PREFIXES

logger = logging.getLogger(__name__)

# Сигнатуры файлов по magic-байтам: расширение можно подделать, сигнатуру — нет.
MAGIC_BYTES = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.gif': (b'GIF87a', b'GIF89a'),
    '.bmp': (b'BM',),
    '.pdf': (b'%PDF',),
}


class FileSaver:
    """Класс для сохранения файлов в папку docs."""

    @staticmethod
    def check_magic(file_path: str) -> tuple[bool, str]:
        """Проверить, что содержимое файла соответствует его расширению."""
        ext = os.path.splitext(file_path)[1].lower()
        signatures = MAGIC_BYTES.get(ext)
        if not signatures:
            return False, f"Недопустимый формат: {ext}"
        try:
            with open(file_path, 'rb') as f:
                head = f.read(8)
        except OSError as e:
            return False, f"Не удалось прочитать файл: {e}"
        if not any(head.startswith(sig) for sig in signatures):
            return False, f"Содержимое файла не соответствует расширению {ext}"
        return True, ""

    @staticmethod
    def validate_file(file_path: str, file_size: int = 0) -> tuple[bool, str]:
        """
        Валидация файла по размеру и расширению.

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

        # Проверка расширения — единый список из config
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Недопустимый формат: {ext}. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"

        return True, ""

    @staticmethod
    def save_document(temp_path: str, worker_id: str, doc_type: str, index: int = 1) -> str:
        """
        Сохранить документ в папку docs с правильным именем.

        Args:
            temp_path: путь к временному файлу
            worker_id: ID работника
            doc_type: тип документа (ключ из DOC_FLOWS)
            index: номер файла для multi_file документов (1 = без суффикса)

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

        # Папка для документов работника
        worker_dir = os.path.join(DOCS_DIR, worker_id)
        os.makedirs(worker_dir, exist_ok=True)

        new_filename = f"{prefix}{ext}" if index <= 1 else f"{prefix}_{index}{ext}"
        new_path = os.path.join(worker_dir, new_filename)

        try:
            os.replace(temp_path, new_path)
        except OSError:
            shutil.copy2(temp_path, new_path)
            os.remove(temp_path)
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
