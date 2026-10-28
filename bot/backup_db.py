"""
Скрипт бэкапа SQLite базы данных.

Запуск: python bot/backup_db.py
"""
import os
import sys
import shutil

# Пути
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)

from config import DB_PATH, PROJECT_ROOT
from shared import now_msk

BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")


def backup_db():
    """Создать бэкап БД."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = now_msk().strftime("%Y%m%d_%H%M%S")
    backup_name = f"users_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    if not os.path.exists(DB_PATH):
        print(f"БД не найдена: {DB_PATH}")
        return None

    shutil.copy2(DB_PATH, backup_path)
    size_kb = os.path.getsize(backup_path) / 1024
    print(f"Бэкап создан: {backup_path} ({size_kb:.1f} KB)")

    # Удаляем старые бэкапы (оставляем последние 10)
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')],
        reverse=True
    )
    for old in backups[10:]:
        os.remove(os.path.join(BACKUP_DIR, old))
        print(f"Удалён старый бэкап: {old}")

    return backup_path


if __name__ == "__main__":
    backup_db()
