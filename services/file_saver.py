"""
Сервис для сохранения файлов
"""
import os
import logging
from config import DOCS_DIR, DOC_PREFIXES

logger = logging.getLogger(__name__)

class FileSaver:
    """Класс для сохранения файлов в папку docs"""
    
    @staticmethod
    def save_document(temp_path: str, worker_id: str, doc_type: str) -> str:
        """
        Сохранить документ в папку docs с правильным именем

        Args:
            temp_path: путь к временному файлу
            worker_id: ID работника
            doc_type: тип документа (photo, passport, patent, registration)

        Returns:
            имя сохраненного файла
        """
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Временный файл не найден: {temp_path}")

        prefix = DOC_PREFIXES.get(doc_type, 'doc')
        ext = os.path.splitext(temp_path)[1].lower()

        new_filename = f"{prefix}_{worker_id}{ext}"
        new_path = os.path.join(DOCS_DIR, new_filename)

        os.rename(temp_path, new_path)
        logger.info("Сохранен документ: %s", new_filename)

        return new_filename
    
    @staticmethod
    def cleanup_temp_files(file_paths: list):
        """Очистить временные файлы"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении {file_path}: {e}")