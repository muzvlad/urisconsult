"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден. Создайте файл .env с BOT_TOKEN=ваш_токен")

# Пути к папкам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "Users")
DOCS_DIR = os.path.join(USERS_DIR, "docs")

# Создаем папки если их нет
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Форматы файлов
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.pdf']

# Префиксы для документов
DOC_PREFIXES = {
    'photo': 'photo',
    'passport': 'pas',
    'patent': 'pat',
    'registration': 'reg'
}

# Соответствие полей JSON и документов
JSON_DOC_FIELDS = {
    'photo': 'photo',
    'passport': 'Паспорт',
    'patent': 'Патент',
    'registration': 'Регистрация'
}