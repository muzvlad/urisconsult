"""
Сервис для сохранения данных в JSON
"""
import os
import json
import re
import logging
import threading
from datetime import datetime
from config import USERS_DIR, JSON_DOC_FIELDS

logger = logging.getLogger(__name__)

_write_lock = threading.Lock()

class JSONSaver:
    """Класс для сохранения данных в JSON файлы"""
    
    @staticmethod
    def get_next_id() -> str:
        """Получить следующий доступный ID"""
        existing_files = [f for f in os.listdir(USERS_DIR) if f.endswith('.json')]
        if not existing_files:
            return "00001"
        
        ids = []
        for filename in existing_files:
            try:
                with open(os.path.join(USERS_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'id' in data:
                        ids.append(int(data['id']))
            except (json.JSONDecodeError, KeyError, ValueError):
                match = re.search(r'(\d+)', filename)
                if match:
                    ids.append(int(match.group(1)))
        
        if not ids:
            return "00001"
        
        next_id = max(ids) + 1
        return str(next_id).zfill(5)
    
    @staticmethod
    def generate_filename(name: str) -> str:
        """Сгенерировать имя файла из ФИО"""
        name_parts = name.split()
        if len(name_parts) >= 3:
            return f"{name_parts[0]} {name_parts[1]} {name_parts[2]}.json"
        elif len(name_parts) == 2:
            return f"{name_parts[0]} {name_parts[1]}.json"
        else:
            return f"{name}.json"
    
    @staticmethod
    def save_worker_data(user_id: int, data: dict, telegram_username: str = None) -> tuple:
        """
        Сохранить данные работника в JSON файл

        Args:
            user_id: ID пользователя в Telegram
            data: словарь с данными
            telegram_username: username в Telegram

        Returns:
            tuple: (worker_id, filename)
        """
        with _write_lock:
            worker_id = data.get('id', JSONSaver.get_next_id())
            data['id'] = worker_id

            filename = JSONSaver.generate_filename(data['name'])
            filepath = os.path.join(USERS_DIR, filename)

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
            data.pop('photo_temp_path', None)
            data.pop('passport_temp_path', None)
            data.pop('patent_temp_path', None)
            data.pop('registration_temp_path', None)
            data.pop('editing_field', None)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info("Сохранен файл: %s с ID %s", filename, worker_id)
            return worker_id, filename