"""
Сервис для сохранения данных в SQLite (нормализованная схема).
"""
import json
from datetime import datetime
from config.documents import DOC_FLOWS
from services import db


class DBSaver:
    """Класс для сохранения данных в SQLite базу."""

    @staticmethod
    async def get_next_id() -> str:
        """Получить следующий доступный ID."""
        return await db.get_next_id()

    @staticmethod
    async def save_worker_data(user_id: int, data: dict, telegram_username: str = None) -> tuple:
        """
        Сохранить данные работника в БД.

        Если анкета была отклонена — статус меняется на 'pending' (ожидает обработки).

        Args:
            user_id: ID пользователя в Telegram
            data: словарь с данными (включая temp_path ключи для документов)
            telegram_username: username в Telegram

        Returns:
            tuple: (worker_id, name)
        """
        worker_id = data.get('id', await db.get_next_id())
        data['id'] = worker_id

        # Определяем статус: если было исправление — ставим 'pending'
        editing_rejected = data.get('editing_rejected', False)
        status = 'pending' if editing_rejected else data.get('status', 'pending')

        # Подготавливаем личные данные
        save_data = {
            'id': worker_id,
            'name': data.get('name', ''),
            'citizenship': data.get('citizenship', ''),
            'gender': data.get('gender', ''),
            'position': data.get('position', ''),
            'object': data.get('object', ''),
            'object_address': data.get('object_address', ''),
            'manager': data.get('manager', ''),
            'phone_main': data.get('phone_main', ''),
            'phone_additional': data.get('phone_additional', ''),
            'email': data.get('email', ''),
            'date': data.get('date', ''),
            'registration': data.get('registration', ''),
            'marital_status': data.get('russia_marital_status', ''),
            'relatives_json': json.dumps(data.get('russia_relatives_list', []), ensure_ascii=False),
            'created_at': datetime.now().isoformat(),
            'telegram_id': user_id,
            'status': status,
            'rejection_reasons': '[]',
        }
        if telegram_username:
            save_data['telegram_username'] = telegram_username

        # Сохраняем работника
        await db.save_worker(save_data)

        # Сохраняем документы (из saved_files — финальные имена файлов)
        doc_files = {}
        if 'saved_files' in data:
            doc_files.update(data['saved_files'])

        if doc_files:
            await db.save_documents(worker_id, doc_files)

        return worker_id, data.get('name', '')
