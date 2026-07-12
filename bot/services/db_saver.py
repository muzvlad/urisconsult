"""
Сервис для сохранения данных в SQLite
"""
import asyncio
from datetime import datetime
from config import JSON_DOC_FIELDS
from services import db


class DBSaver:
    """Класс для сохранения данных в SQLite базу"""

    @staticmethod
    async def get_next_id() -> str:
        """Получить следующий доступный ID"""
        return await db.get_next_id()

    @staticmethod
    async def save_worker_data(user_id: int, data: dict, telegram_username: str = None) -> tuple:
        """
        Сохранить данные работника в БД

        Args:
            user_id: ID пользователя в Telegram
            data: словарь с данными
            telegram_username: username в Telegram

        Returns:
            tuple: (worker_id, unused_name)
        """
        worker_id = data.get('id', await db.get_next_id())
        data['id'] = worker_id

        data['created_at'] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        data['telegram_id'] = user_id
        if telegram_username:
            data['telegram_username'] = telegram_username

        if 'saved_files' in data:
            for doc_type, saved_filename in data['saved_files'].items():
                json_field = JSON_DOC_FIELDS.get(doc_type)
                if json_field:
                    data[json_field] = saved_filename

        data.pop('saved_files', None)
        data.pop('temp_files', None)
        data.pop('editing_field', None)
        
        # Удаляем все временные пути документов
        temp_keys = [key for key in data.keys() if key.endswith('_temp_path')]
        for key in temp_keys:
            data.pop(key, None)

        await db.save_worker(data)
        return worker_id, data.get('name', '')
