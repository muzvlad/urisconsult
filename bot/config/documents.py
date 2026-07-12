"""
Единый источник истины для типов документов.

Все префиксы файлов, маппинги, порядок документов — ОДИН раз здесь.
При добавлении нового типа документа править ТОЛЬКО этот файл.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DocumentType:
    """Описание одного типа документа."""
    key: str              # Уникальный ключ (BN поле в БД)
    label: str            # Человекочитаемое название
    prefix: str           # Префикс для имени файла: {prefix}_{worker_id}.{ext}
    required: bool = False
    can_skip: bool = True
    category: str = ''    # Категория гражданства (заполняется автоматически)


# ─── Определяем все типы документов ────────────────────────────

# Общие документы (все категории)
_PHOTO = DocumentType(key='photo', label='Фото', prefix='photo', required=True)
_PASSPORT = DocumentType(key='passport', label='Паспорт', prefix='pas', required=True)

# Патент
_PATENT_SNILS = DocumentType(key='patent_snils', label='СНИЛС', prefix='snils')
_PATENT_REGISTRATION = DocumentType(key='patent_registration', label='Регистрация', prefix='reg')
_PATENT_MIGRATION_CARD = DocumentType(key='patent_migration_card', label='Миграционная карта', prefix='mig')
_PATENT_DMS = DocumentType(key='patent_dms', label='ДМС', prefix='dms')
_PATENT_PATENT = DocumentType(key='patent_patent', label='Патент', prefix='pat')
_PATENT_INN = DocumentType(key='patent_inn', label='ИНН', prefix='inn', can_skip=True)
_PATENT_RECEIPT = DocumentType(key='patent_receipt', label='Чек по патенту', prefix='chek')
_PATENT_LANGUAGE_CERT = DocumentType(key='patent_language_cert', label='Сертификат о знании языка', prefix='lang')
_PATENT_BANK_DETAILS = DocumentType(key='patent_bank_details', label='Реквизиты банковской карты', prefix='bank')
_PATENT_FINGERPRINT_CARD = DocumentType(key='patent_fingerprint_card', label='Дактилоскопическая карта', prefix='dactyl')

# Студент
_STUDENT_SNILS = DocumentType(key='student_snils', label='СНИЛС', prefix='snils')
_STUDENT_REGISTRATION = DocumentType(key='student_registration', label='Регистрация', prefix='reg')
_STUDENT_MIGRATION_CARD = DocumentType(key='student_migration_card', label='Миграционная карта', prefix='mig')
_STUDENT_DMS = DocumentType(key='student_dms', label='ДМС', prefix='dms')
_STUDENT_INN = DocumentType(key='student_inn', label='ИНН', prefix='inn')
_STUDENT_FINGERPRINT_CARD = DocumentType(key='student_fingerprint_card', label='Дактилоскопическая карта', prefix='dactyl')
_STUDENT_UNIVERSITY_CERT = DocumentType(key='student_university_cert', label='Справка из ВУЗа', prefix='spravka')
_STUDENT_BANK_DETAILS = DocumentType(key='student_bank_details', label='Реквизиты банковской карты', prefix='bank')

# ЕАЭС
_EAEAS_REGISTRATION = DocumentType(key='eaeas_registration', label='Регистрация', prefix='reg')
_EAEAS_MIGRATION_CARD = DocumentType(key='eaeas_migration_card', label='Миграционная карта', prefix='mig')
_EAEAS_DMS = DocumentType(key='eaeas_dms', label='ДМС', prefix='dms')
_EAEAS_INN = DocumentType(key='eaeas_inn', label='ИНН', prefix='inn')
_EAEAS_SNILS = DocumentType(key='eaeas_snils', label='СНИЛС', prefix='snils')
_EAEAS_FINGERPRINT_CARD = DocumentType(key='eaeas_fingerprint_card', label='Дактилоскопическая карта', prefix='dactyl')
_EAEAS_BANK_DETAILS = DocumentType(key='eaeas_bank_details', label='Реквизиты банковской карты', prefix='bank')

# РВП
_RVP_MIGRATION_CARD = DocumentType(key='rvp_migration_card', label='Миграционная карта', prefix='mig')
_RVP_DMS_OMS = DocumentType(key='rvp_dms_oms', label='ДМС/ОМС', prefix='dms')
_RVP_INN = DocumentType(key='rvp_inn', label='ИНН', prefix='inn')
_RVP_SNILS = DocumentType(key='rvp_snils', label='СНИЛС', prefix='snils')
_RVP_BANK_DETAILS = DocumentType(key='rvp_bank_details', label='Реквизиты банковской карты', prefix='bank')

# ВНЖ
_VNZH_MIGRATION_CARD = DocumentType(key='vnzh_migration_card', label='Миграционная карта', prefix='mig', can_skip=True)
_VNZH_VNZH = DocumentType(key='vnzh_vnzh', label='ВНЖ', prefix='vnzh')
_VNZH_DMS_OMS = DocumentType(key='vnzh_dms_oms', label='ДМС/ОМС', prefix='dms')
_VNZH_INN = DocumentType(key='vnzh_inn', label='ИНН', prefix='inn')
_VNZH_SNILS = DocumentType(key='vnzh_snils', label='СНИЛС', prefix='snils')
_VNZH_WORK_BOOK = DocumentType(key='vnzh_work_book', label='Трудовая книжка/ЭТК', prefix='trud')
_VNZH_BANK_DETAILS = DocumentType(key='vnzh_bank_details', label='Реквизиты банковской карты', prefix='bank')

# Россия
_RUSSIA_PASSPORT_PROPISKA = DocumentType(key='russia_passport_propiska', label='Паспорт прописка', prefix='propiska')
_RUSSIA_PROPISKA = DocumentType(key='russia_propiska', label='Прописка', prefix='propiska')
_RUSSIA_INN = DocumentType(key='russia_inn', label='ИНН', prefix='inn')
_RUSSIA_SNILS = DocumentType(key='russia_snils', label='СНИЛС', prefix='snils')
_RUSSIA_EDUCATION_DOC = DocumentType(key='russia_education_doc', label='Документ об образовании', prefix='edu', can_skip=True)
_RUSSIA_WORK_BOOK = DocumentType(key='russia_work_book', label='Трудовая книжка/ЭТК', prefix='trud')
_RUSSIA_MILITARY_DOC = DocumentType(key='russia_military_doc', label='Военный билет/Приписное', prefix='voen', can_skip=True)


# ─── Порядок документов по категориям (порядок = порядок запроса) ──────

DOC_FLOWS: Dict[str, List[DocumentType]] = {
    'Патент': [
        _PHOTO, _PASSPORT,
        _PATENT_SNILS, _PATENT_REGISTRATION, _PATENT_MIGRATION_CARD,
        _PATENT_DMS, _PATENT_PATENT, _PATENT_INN, _PATENT_RECEIPT,
        _PATENT_LANGUAGE_CERT, _PATENT_BANK_DETAILS, _PATENT_FINGERPRINT_CARD,
    ],
    'Студент': [
        _PHOTO, _PASSPORT,
        _STUDENT_SNILS, _STUDENT_REGISTRATION, _STUDENT_MIGRATION_CARD,
        _STUDENT_DMS, _STUDENT_INN, _STUDENT_FINGERPRINT_CARD,
        _STUDENT_UNIVERSITY_CERT, _STUDENT_BANK_DETAILS,
    ],
    'ЕАЭС': [
        _PHOTO, _PASSPORT,
        _EAEAS_REGISTRATION, _EAEAS_MIGRATION_CARD, _EAEAS_DMS,
        _EAEAS_INN, _EAEAS_SNILS, _EAEAS_FINGERPRINT_CARD,
        _EAEAS_BANK_DETAILS,
    ],
    'РВП': [
        _PHOTO, _PASSPORT,
        _RVP_MIGRATION_CARD, _RVP_DMS_OMS, _RVP_INN,
        _RVP_SNILS, _RVP_BANK_DETAILS,
    ],
    'ВНЖ': [
        _PHOTO, _PASSPORT,
        _VNZH_MIGRATION_CARD, _VNZH_VNZH, _VNZH_DMS_OMS,
        _VNZH_INN, _VNZH_SNILS, _VNZH_WORK_BOOK, _VNZH_BANK_DETAILS,
    ],
    'Россия': [
        _PHOTO, _PASSPORT,
        _RUSSIA_PASSPORT_PROPISKA, _RUSSIA_INN, _RUSSIA_SNILS,
        _RUSSIA_EDUCATION_DOC, _RUSSIA_WORK_BOOK, _RUSSIA_MILITARY_DOC,
    ],
}

# Автозаполняем category в каждом DocumentType
for _cat_name, _cat_docs in DOC_FLOWS.items():
    for _doc in _cat_docs:
        object.__setattr__(_doc, 'category', _cat_name)


# ─── Производные маппинги (авто-генерация из DOC_FLOWS) ──────────────

# {doc_key: prefix} — для file_saver
DOC_PREFIXES: Dict[str, str] = {
    doc.key: doc.prefix
    for docs in DOC_FLOWS.values()
    for doc in docs
}

# {doc_key: label} — для отображения / БД маппинга
DOC_LABELS: Dict[str, str] = {
    doc.key: doc.label
    for docs in DOC_FLOWS.values()
    for doc in docs
}

# {category: [doc_key, ...]} — для UI и поиска
CITIZENSHIP_DOC_KEYS: Dict[str, List[str]] = {
    cat: [doc.key for doc in docs]
    for cat, docs in DOC_FLOWS.items()
}


# ─── Промпты для документов (тексты для бота) ────────────────────────

DOC_PROMPTS: Dict[str, str] = {
    'photo': '📸 Отправьте фото (селфи):',
    'passport': '🪪 Отправьте паспорт в развороте:',
    'patent_snils': '📄 Отправьте СНИЛС (или перевод паспорта):',
    'patent_registration': '📋 Отправьте регистрацию:',
    'patent_migration_card': '🎫 Отправьте миграционную карту:',
    'patent_dms': '🏥 Отправьте ДМС:',
    'patent_patent': '📝 Отправьте патент:',
    'patent_inn': '🔢 Отправьте ИНН (можно пропустить):',
    'patent_receipt': '🧾 Отправьте чек по патенту:',
    'patent_language_cert': '🎓 Отправьте сертификат о знании языка:',
    'patent_bank_details': '💳 Отправьте реквизиты банковской карты:',
    'patent_fingerprint_card': '🖐 Отправьте дактилоскопическую карту:',
    'student_snils': '📄 Отправьте СНИЛС (или перевод паспорта):',
    'student_registration': '📋 Отправьте регистрацию:',
    'student_migration_card': '🎫 Отправьте миграционную карту:',
    'student_dms': '🏥 Отправьте ДМС:',
    'student_inn': '🔢 Отправьте ИНН:',
    'student_fingerprint_card': '🖐 Отправьте дактилоскопическую карту:',
    'student_university_cert': '🎓 Отправьте справку из ВУЗа:',
    'student_bank_details': '💳 Отправьте реквизиты счета банковской карты:',
    'eaeas_registration': '📋 Отправьте регистрацию:',
    'eaeas_migration_card': '🎫 Отправьте миграционную карту:',
    'eaeas_dms': '🏥 Отправьте ДМС:',
    'eaeas_inn': '🔢 Отправьте ИНН:',
    'eaeas_snils': '📄 Отправьте СНИЛС:',
    'eaeas_fingerprint_card': '🖐 Отправьте дактилоскопическую карту:',
    'eaeas_bank_details': '💳 Отправьте реквизиты счета банковской карты:',
    'rvp_migration_card': '🎫 Отправьте миграционную карту:',
    'rvp_dms_oms': '🏥 Отправьте ДМС или ОМС:',
    'rvp_inn': '🔢 Отправьте ИНН:',
    'rvp_snils': '📄 Отправьте СНИЛС:',
    'rvp_bank_details': '💳 Отправьте реквизиты счета банковской карты:',
    'vnzh_migration_card': '🎫 Отправьте миграционную карту (желательно):',
    'vnzh_vnzh': '🪪 Отправьте ВНЖ:',
    'vnzh_dms_oms': '🏥 Отправьте ДМС или ОМС:',
    'vnzh_inn': '🔢 Отправьте ИНН:',
    'vnzh_snils': '📄 Отправьте СНИЛС:',
    'vnzh_work_book': '📖 Отправьте трудовую книжку или ЭТК с Госуслуг:',
    'vnzh_bank_details': '💳 Отправьте реквизиты счета банковской карты:',
    'russia_passport_propiska': '📖 Отправьте паспорт (разворот прописки):',
    'russia_propiska': '📋 Отправьте прописку:',
    'russia_inn': '🔢 Отправьте ИНН:',
    'russia_snils': '📄 Отправьте СНИЛС:',
    'russia_education_doc': '🎓 Отправьте документ об образовании (или пропустите):',
    'russia_work_book': '📖 Отправьте трудовую книжку или ЭТК с Госуслуг:',
    'russia_military_doc': '🎖 Отправьте военный билет или приписное (или пропустите):',
}


def get_doc_flow(citizenship: str) -> List[DocumentType]:
    """Получить список документов для категории гражданства."""
    return DOC_FLOWS.get(citizenship, DOC_FLOWS['Патент'])


def get_next_doc(current_doc_key: str, citizenship: str) -> Optional[DocumentType]:
    """Получить следующий документ в цепочке после current_doc_key."""
    flow = get_doc_flow(citizenship)
    for i, doc in enumerate(flow):
        if doc.key == current_doc_key:
            if i + 1 < len(flow):
                return flow[i + 1]
            return None
    return None


def get_doc_by_key(doc_key: str) -> Optional[DocumentType]:
    """Найти DocumentType по ключу."""
    for docs in DOC_FLOWS.values():
        for doc in docs:
            if doc.key == doc_key:
                return doc
    return None
