"""
Скрипт для генерации 5 тестовых анкет (Тестовый*) для визуального теста UI.

Запуск: cd bot && python seed_test_data.py
"""
import os
import sys
import asyncio
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, USERS_DIR, DOCS_DIR
from config.documents import DOC_FLOWS


TEST_WORKERS = [
    {
        'id': '00001',
        'name': 'Тестовы Алексей Сергеевич',
        'citizenship': 'Патент',
        'gender': 'Мужской',
        'position': 'Электрик',
        'object': 'Жилой дом "Пушкинский"',
        'object_address': 'ул. Пушкина, д. 10, кв. 25',
        'manager': 'Иванов И.И.',
        'phone_main': '+79991112233',
        'phone_additional': '+79993334455',
        'email': 'testovyi.alexey@mail.ru',
        'date': '15.03.1992',
        'registration': 'Регистрация до 31.12.2026',
        'status': 'pending',
    },
    {
        'id': '00002',
        'name': 'Тестовая Мария Петровна',
        'citizenship': 'Студент',
        'gender': 'Женский',
        'position': 'Администратор',
        'object': 'Офис "Центр"',
        'object_address': 'пр. Мира, д. 25, офис 312',
        'manager': 'Петров П.П.',
        'phone_main': '+79992223344',
        'phone_additional': 'Не указана',
        'email': 'testovaya.maria@gmail.com',
        'date': '22.07.1998',
        'registration': 'Регистрация до 01.09.2027',
        'status': 'accepted',
    },
    {
        'id': '00003',
        'name': 'Тестовый Дмитрий Александрович',
        'citizenship': 'ЕАЭС',
        'gender': 'Мужской',
        'position': 'Грузчик',
        'object': 'Склад "Логистик"',
        'object_address': 'ул. Складочная, д. 1, стр. 5',
        'manager': 'Козлов К.К.',
        'phone_main': '+79994445566',
        'phone_additional': 'Не указан',
        'email': 'testovyi.dmitry@yandex.ru',
        'date': '10.11.1988',
        'registration': 'Регистрация до 15.06.2026',
        'status': 'pending',
    },
    {
        'id': '00004',
        'name': 'Тестовая Елена Владимировна',
        'citizenship': 'Россия',
        'gender': 'Женский',
        'position': 'Бухгалтер',
        'object': 'ООО "Рога и Копыта"',
        'object_address': 'ул. Деловая, д. 42, каб. 101',
        'manager': 'Сидоров С.С.',
        'phone_main': '+79995556677',
        'phone_additional': '+79997778899',
        'email': 'testovaya.elena@bk.ru',
        'date': '05.01.1995',
        'registration': 'Постоянная прописка',
        'status': 'rejected',
        'rejection_reasons': '["email", "phone_additional"]',
    },
    {
        'id': '00005',
        'name': 'Тестовый Олег Николаевич',
        'citizenship': 'ВНЖ',
        'gender': 'Мужской',
        'position': 'Сварщик',
        'object': 'Завод "Металлист"',
        'object_address': 'ул. Промышленная, д. 7',
        'manager': 'Никонов Н.Н.',
        'phone_main': '+79998889900',
        'phone_additional': 'Не указан',
        'email': 'testovyi.oleg@mail.ru',
        'date': '18.09.1990',
        'registration': 'ВНЖ до 20.03.2028',
        'status': 'pending',
    },
]


def create_test_workers():
    """Создать 5 тестовых работников в БД."""
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Создаём таблицы если их нет
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            citizenship TEXT,
            gender TEXT,
            position TEXT,
            object TEXT,
            object_address TEXT,
            manager TEXT,
            phone_main TEXT,
            phone_additional TEXT,
            email TEXT,
            date TEXT,
            registration TEXT,
            marital_status TEXT,
            relatives_json TEXT DEFAULT '[]',
            telegram_id INTEGER,
            telegram_username TEXT,
            created_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            date TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)

    # Добавляем колонки status и rejection_reasons если их нет
    try:
        conn.execute("ALTER TABLE workers ADD COLUMN status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE workers ADD COLUMN rejection_reasons TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass

    # Вставляем работников
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    for w in TEST_WORKERS:
        conn.execute("""
            INSERT OR REPLACE INTO workers
            (id, name, citizenship, gender, position, object, object_address,
             manager, phone_main, phone_additional, email, date, registration,
             status, rejection_reasons, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            w['id'], w['name'], w['citizenship'], w['gender'], w['position'],
            w['object'], w['object_address'], w['manager'],
            w['phone_main'], w['phone_additional'], w['email'], w['date'],
            w['registration'], w.get('status', 'pending'),
            w.get('rejection_reasons', '[]'), now
        ))

    conn.commit()
    conn.close()
    print(f"Создано {len(TEST_WORKERS)} тестовых анкет в {DB_PATH}")

    for w in TEST_WORKERS:
        status_icon = {'pending': '⏳', 'accepted': '✅', 'rejected': '❌'}.get(w['status'], '?')
        print(f"  {status_icon} {w['id']} — {w['name']} ({w['citizenship']}, {w['status']})")


if __name__ == "__main__":
    create_test_workers()
