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
PROJECT_ROOT = os.path.dirname(BASE_DIR)
USERS_DIR = os.path.join(BASE_DIR, "Users")
DB_PATH = os.path.join(USERS_DIR, "users.db")
DOCS_DIR = os.path.join(PROJECT_ROOT, "users", "docs")

# Создаем папки если их нет
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Форматы файлов
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.pdf']

# Префиксы для документов
DOC_PREFIXES = {
    'photo': 'photo',
    'passport': 'pas',
    'patent_snils': 'snils',
    'patent_registration': 'reg',
    'patent_migration_card': 'mig',
    'patent_dms': 'dms',
    'patent_patent': 'pat',
    'patent_inn': 'inn',
    'patent_receipt': 'chek',
    'patent_language_cert': 'lang',
    'patent_bank_details': 'bank',
    'patent_fingerprint_card': 'dactyl',
    'student_snils': 'snils',
    'student_registration': 'reg',
    'student_migration_card': 'mig',
    'student_dms': 'dms',
    'student_inn': 'inn',
    'student_fingerprint_card': 'dactyl',
    'student_university_cert': 'spravka',
    'student_bank_details': 'bank',
    'eaeas_registration': 'reg',
    'eaeas_migration_card': 'mig',
    'eaeas_dms': 'dms',
    'eaeas_inn': 'inn',
    'eaeas_snils': 'snils',
    'eaeas_fingerprint_card': 'dactyl',
    'eaeas_bank_details': 'bank',
    'rvp_migration_card': 'mig',
    'rvp_dms_oms': 'dms',
    'rvp_inn': 'inn',
    'rvp_snils': 'snils',
    'rvp_bank_details': 'bank',
    'vnzh_migration_card': 'mig',
    'vnzh_vnzh': 'vnzh',
    'vnzh_dms_oms': 'dms',
    'vnzh_inn': 'inn',
    'vnzh_snils': 'snils',
    'vnzh_work_book': 'trud',
    'vnzh_bank_details': 'bank',
    'russia_passport_propiska': 'propiska',
    'russia_propiska': 'propiska',
    'russia_inn': 'inn',
    'russia_snils': 'snils',
    'russia_education_doc': 'edu',
    'russia_work_book': 'trud',
    'russia_military_doc': 'voen',
    'registration': 'reg'
}

# Соответствие полей JSON и документов
JSON_DOC_FIELDS = {
    'photo': 'photo',
    'passport': 'Паспорт',
    'patent_snils': 'СНИЛС',
    'patent_registration': 'Регистрация',
    'patent_migration_card': 'Миграционная карта',
    'patent_dms': 'ДМС',
    'patent_patent': 'Патент',
    'patent_inn': 'ИНН',
    'patent_receipt': 'Чек по патенту',
    'patent_language_cert': 'Сертификат о знании языка',
    'patent_bank_details': 'Реквизиты банковской карты',
    'patent_fingerprint_card': 'Дактилоскопическая карта',
    'student_snils': 'СНИЛС',
    'student_registration': 'Регистрация',
    'student_migration_card': 'Миграционная карта',
    'student_dms': 'ДМС',
    'student_inn': 'ИНН',
    'student_fingerprint_card': 'Дактилоскопическая карта',
    'student_university_cert': 'Справка из ВУЗа',
    'student_bank_details': 'Реквизиты банковской карты',
    'eaeas_registration': 'Регистрация',
    'eaeas_migration_card': 'Миграционная карта',
    'eaeas_dms': 'ДМС',
    'eaeas_inn': 'ИНН',
    'eaeas_snils': 'СНИЛС',
    'eaeas_fingerprint_card': 'Дактилоскопическая карта',
    'eaeas_bank_details': 'Реквизиты банковской карты',
    'rvp_migration_card': 'Миграционная карта',
    'rvp_dms_oms': 'ДМС/ОМС',
    'rvp_inn': 'ИНН',
    'rvp_snils': 'СНИЛС',
    'rvp_bank_details': 'Реквизиты банковской карты',
    'vnzh_migration_card': 'Миграционная карта',
    'vnzh_vnzh': 'ВНЖ',
    'vnzh_dms_oms': 'ДМС/ОМС',
    'vnzh_inn': 'ИНН',
    'vnzh_snils': 'СНИЛС',
    'vnzh_work_book': 'Трудовая книжка/ЭТК',
    'vnzh_bank_details': 'Реквизиты банковской карты',
    'russia_passport_propiska': 'Паспорт прописка',
    'russia_propiska': 'Прописка',
    'russia_inn': 'ИНН',
    'russia_snils': 'СНИЛС',
    'russia_education_doc': 'Документ об образовании',
    'russia_work_book': 'Трудовая книжка/ЭТК',
    'russia_military_doc': 'Военный билет/Приписное',
    'registration': 'Регистрация'
}