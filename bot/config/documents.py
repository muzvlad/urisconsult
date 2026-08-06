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
_PATENT_PASSPORT_TRANSLATION = DocumentType(key='patent_passport_translation', label='Перевод паспорта', prefix='pas_trans')
_PATENT_SNILS = DocumentType(key='patent_snils', label='СНИЛС', prefix='snils')
_PATENT_REGISTRATION = DocumentType(key='patent_registration', label='Регистрация (лицевая) / скрин Амина', prefix='reg')
_PATENT_REGISTRATION_BACK = DocumentType(key='patent_registration_back', label='Регистрация (оборотная)', prefix='reg_back', can_skip=True)
_PATENT_MIGRATION_CARD = DocumentType(key='patent_migration_card', label='Миграционная карта', prefix='mig')
_PATENT_DMS = DocumentType(key='patent_dms', label='ДМС', prefix='dms')
_PATENT_PATENT_FRONT = DocumentType(key='patent_patent_front', label='Патент (лицевая)', prefix='pat_front')
_PATENT_PATENT_BACK = DocumentType(key='patent_patent_back', label='Патент (разворот)', prefix='pat_back')
_PATENT_INN = DocumentType(key='patent_inn', label='ИНН', prefix='inn', can_skip=True)
_PATENT_RECEIPT_1 = DocumentType(key='patent_receipt_1', label='Чек по патенту 1', prefix='chek1')
_PATENT_RECEIPT_2 = DocumentType(key='patent_receipt_2', label='Чек по патенту 2', prefix='chek2')
_PATENT_RECEIPT_3 = DocumentType(key='patent_receipt_3', label='Чек по патенту 3', prefix='chek3')
_PATENT_RECEIPT_4 = DocumentType(key='patent_receipt_4', label='Чек по патенту 4', prefix='chek4')
_PATENT_RECEIPT_5 = DocumentType(key='patent_receipt_5', label='Чек по патенту 5', prefix='chek5')
_PATENT_RECEIPT_6 = DocumentType(key='patent_receipt_6', label='Чек по патенту 6', prefix='chek6')
_PATENT_RECEIPT_7 = DocumentType(key='patent_receipt_7', label='Чек по патенту 7', prefix='chek7')
_PATENT_RECEIPT_8 = DocumentType(key='patent_receipt_8', label='Чек по патенту 8', prefix='chek8')
_PATENT_RECEIPT_9 = DocumentType(key='patent_receipt_9', label='Чек по патенту 9', prefix='chek9')
_PATENT_RECEIPT_10 = DocumentType(key='patent_receipt_10', label='Чек по патенту 10', prefix='chek10')
_PATENT_RECEIPT_11 = DocumentType(key='patent_receipt_11', label='Чек по патенту 11', prefix='chek11')
_PATENT_LANGUAGE_CERT = DocumentType(key='patent_language_cert', label='Сертификат о знании языка', prefix='lang')
_PATENT_BANK_DETAILS = DocumentType(key='patent_bank_details', label='Реквизиты банковской карты', prefix='bank')
_PATENT_FINGERPRINT_FRONT = DocumentType(key='patent_fingerprint_front', label='Дактилоскопия (лицевая)', prefix='dactyl_front')
_PATENT_FINGERPRINT_BACK = DocumentType(key='patent_fingerprint_back', label='Дактилоскопия (разворот)', prefix='dactyl_back')

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
_EAEAS_PASSPORT = DocumentType(key='eaeas_passport', label='Паспорт или идентификационная карта (лицевая)', prefix='pas', required=True)
_EAEAS_PASSPORT_BACK = DocumentType(key='eaeas_passport_back', label='Идентификационная карта (разворот)', prefix='pas_back', can_skip=True)
_EAEAS_PASSPORT_TRANSLATION = DocumentType(key='eaeas_passport_translation', label='Перевод паспорта', prefix='pas_trans')
_EAEAS_REGISTRATION = DocumentType(key='eaeas_registration', label='Регистрация (лицевая) / скрин Амина', prefix='reg')
_EAEAS_REGISTRATION_BACK = DocumentType(key='eaeas_registration_back', label='Регистрация (оборотная)', prefix='reg_back', can_skip=True)
_EAEAS_MIGRATION_CARD = DocumentType(key='eaeas_migration_card', label='Миграционная карта', prefix='mig')
_EAEAS_DMS = DocumentType(key='eaeas_dms', label='Полис ДМС или ОМС', prefix='dms')
_EAEAS_INN = DocumentType(key='eaeas_inn', label='ИНН', prefix='inn')
_EAEAS_SNILS = DocumentType(key='eaeas_snils', label='СНИЛС', prefix='snils')
_EAEAS_FINGERPRINT_CARD = DocumentType(key='eaeas_fingerprint_card', label='Дактилоскопия (лицевая)', prefix='dactyl')
_EAEAS_FINGERPRINT_BACK = DocumentType(key='eaeas_fingerprint_back', label='Дактилоскопия (разворот)', prefix='dactyl_back')
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
_RUSSIA_INN = DocumentType(key='russia_inn', label='ИНН', prefix='inn')
_RUSSIA_SNILS = DocumentType(key='russia_snils', label='СНИЛС', prefix='snils')
_RUSSIA_EDUCATION_DOC = DocumentType(key='russia_education_doc', label='Документ об образовании', prefix='edu', can_skip=True)
_RUSSIA_WORK_BOOK = DocumentType(key='russia_work_book', label='Трудовая книжка/ЭТК', prefix='trud')
_RUSSIA_MILITARY_DOC = DocumentType(key='russia_military_doc', label='Военный билет/Приписное', prefix='voen', can_skip=True)


# ─── Порядок документов по категориям (порядок = порядок запроса) ──────

DOC_FLOWS: Dict[str, List[DocumentType]] = {
    'Патент': [
        _PHOTO, _PASSPORT,
        _PATENT_PASSPORT_TRANSLATION, _PATENT_MIGRATION_CARD,
        _PATENT_REGISTRATION, _PATENT_REGISTRATION_BACK,
        _PATENT_FINGERPRINT_FRONT, _PATENT_FINGERPRINT_BACK,
        _PATENT_DMS, _PATENT_PATENT_FRONT, _PATENT_PATENT_BACK,
        _PATENT_RECEIPT_1, _PATENT_RECEIPT_2, _PATENT_RECEIPT_3,
        _PATENT_RECEIPT_4, _PATENT_RECEIPT_5, _PATENT_RECEIPT_6,
        _PATENT_RECEIPT_7, _PATENT_RECEIPT_8, _PATENT_RECEIPT_9,
        _PATENT_RECEIPT_10, _PATENT_RECEIPT_11,
        _PATENT_LANGUAGE_CERT, _PATENT_INN, _PATENT_SNILS,
        _PATENT_BANK_DETAILS,
    ],
    'Студент': [
        _PHOTO, _PASSPORT,
        _STUDENT_SNILS, _STUDENT_REGISTRATION, _STUDENT_MIGRATION_CARD,
        _STUDENT_DMS, _STUDENT_INN, _STUDENT_FINGERPRINT_CARD,
        _STUDENT_UNIVERSITY_CERT, _STUDENT_BANK_DETAILS,
    ],
    'ЕАЭС': [
        _PHOTO,
        _EAEAS_PASSPORT, _EAEAS_PASSPORT_BACK,
        _EAEAS_PASSPORT_TRANSLATION,
        _EAEAS_MIGRATION_CARD,
        _EAEAS_REGISTRATION, _EAEAS_REGISTRATION_BACK,
        _EAEAS_FINGERPRINT_CARD, _EAEAS_FINGERPRINT_BACK,
        _EAEAS_DMS,
        _EAEAS_INN, _EAEAS_SNILS, _EAEAS_BANK_DETAILS,
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

# Русские названия ВСЕХ полей (для уведомлений)
FIELD_LABELS: Dict[str, str] = {
    'name': 'ФИО',
    'citizenship': 'Гражданство',
    'gender': 'Пол',
    'position': 'Должность',
    'object': 'Объект',
    'object_address': 'Адрес объекта',
    'manager': 'Менеджер',
    'phone_main': 'Основной телефон',
    'phone_additional': 'Доп. телефон',
    'email': 'Email',
    'date': 'Дата рождения',
    'registration': 'Регистрация',
    'marital_status': 'Семейное положение',
}
# Добавляем labels документов
FIELD_LABELS.update(DOC_LABELS)

# {category: [doc_key, ...]} — для UI и поиска
CITIZENSHIP_DOC_KEYS: Dict[str, List[str]] = {
    cat: [doc.key for doc in docs]
    for cat, docs in DOC_FLOWS.items()
}


# ─── Промпты для документов (тексты для бота) ────────────────────────

DOC_PROMPTS: Dict[str, str] = {
    'photo': '📸 Отправьте фото (селфи):',
    'passport': '🪪 Отправьте паспорт в развороте:',
    'patent_passport_translation': '📄 Отправьте перевод паспорта:',
    'patent_snils': '📄 Отправьте СНИЛС:',
    'patent_registration': '📋 Отправьте регистрацию (лицевая сторона) или скрин из приложения Амина:',
    'patent_registration_back': '📋 Отправьте регистрацию (оборотная сторона) (или пропустите):',
    'patent_migration_card': '🎫 Отправьте миграционную карту:',
    'patent_dms': '🏥 Отправьте ДМС:',
    'patent_patent_front': '📝 Отправьте патент (лицевая сторона):',
    'patent_patent_back': '📝 Отправьте патент (разворот):',
    'patent_inn': '🔢 Отправьте ИНН (можно пропустить):',
    'patent_receipt_1': '🧾 Прикрепите чек по патенту 1:',
    'patent_receipt_2': '🧾 Прикрепите чек по патенту 2 или пропустите:',
    'patent_receipt_3': '🧾 Прикрепите чек по патенту 3 или пропустите:',
    'patent_receipt_4': '🧾 Прикрепите чек по патенту 4 или пропустите:',
    'patent_receipt_5': '🧾 Прикрепите чек по патенту 5 или пропустите:',
    'patent_receipt_6': '🧾 Прикрепите чек по патенту 6 или пропустите:',
    'patent_receipt_7': '🧾 Прикрепите чек по патенту 7 или пропустите:',
    'patent_receipt_8': '🧾 Прикрепите чек по патенту 8 или пропустите:',
    'patent_receipt_9': '🧾 Прикрепите чек по патенту 9 или пропустите:',
    'patent_receipt_10': '🧾 Прикрепите чек по патенту 10 или пропустите:',
    'patent_receipt_11': '🧾 Прикрепите чек по патенту 11 или пропустите:',
    'patent_language_cert': '🎓 Отправьте сертификат о знании языка:',
    'patent_bank_details': '💳 Отправьте реквизиты банковской карты:',
    'patent_fingerprint_front': '🖐 Отправьте дактилоскопию (лицевая сторона):',
    'patent_fingerprint_back': '🖐 Отправьте дактилоскопию (разворот):',
    'student_snils': '📄 Отправьте СНИЛС (или перевод паспорта):',
    'student_registration': '📋 Отправьте регистрацию:',
    'student_migration_card': '🎫 Отправьте миграционную карту:',
    'student_dms': '🏥 Отправьте ДМС:',
    'student_inn': '🔢 Отправьте ИНН:',
    'student_fingerprint_card': '🖐 Отправьте дактилоскопическую карту:',
    'student_university_cert': '🎓 Отправьте справку из ВУЗа:',
    'student_bank_details': '💳 Отправьте реквизиты счета банковской карты:',
    'eaeas_passport': '🪪 Отправьте паспорт (разворот) или идентификационную карту (лицевая сторона):',
    'eaeas_passport_back': '🪪 Если отправляете ID-карту — пришлите разворот (или пропустите):',
    'eaeas_passport_translation': '📄 Отправьте перевод паспорта:',
    'eaeas_registration': '📋 Отправьте регистрацию (лицевая сторона) или скрин из приложения Амина:',
    'eaeas_registration_back': '📋 Отправьте регистрацию (оборотная сторона) (или пропустите):',
    'eaeas_migration_card': '🎫 Отправьте миграционную карту:',
    'eaeas_dms': '🏥 Отправьте полис ДМС или ОМС:',
    'eaeas_inn': '🔢 Отправьте ИНН:',
    'eaeas_snils': '📄 Отправьте СНИЛС:',
    'eaeas_fingerprint_card': '🖐 Отправьте дактилоскопию (лицевая сторона):',
    'eaeas_fingerprint_back': '🖐 Отправьте дактилоскопию (разворот):',
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
