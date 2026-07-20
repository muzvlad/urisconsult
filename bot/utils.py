"""
Общие утилиты для бота.

Централизует повторяющуюся логику:
- получение FSM-состояний для документов
- генерация клавиатур из конфига
- prompts для полей
"""
from typing import Optional, TYPE_CHECKING
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from config.documents import DOC_FLOWS, DOC_LABELS, FIELD_LABELS

if TYPE_CHECKING:
    from aiogram.fsm.state import State


# ─── FSM состояния ───────────────────────────────────────────────────

def get_document_state(doc_key: str) -> Optional["State"]:
    """Получить FSM-состояние для ключа документа."""
    from handlers.registration import get_worker_form
    return getattr(get_worker_form(), doc_key, None)


def get_all_doc_keys() -> set[str]:
    """Получить множество всех ключей документов."""
    keys = set()
    for cat_docs in DOC_FLOWS.values():
        for doc in cat_docs:
            keys.add(doc.key)
    return keys


# ─── Клавиатуры ──────────────────────────────────────────────────────

# Маппинг базовых текстовых полей → (label, callback_suffix)
_BASE_FIELDS = [
    ('name', '📝 ФИО'),
    ('citizenship', '🌍 Гражданство'),
    ('gender', '⚥ Пол'),
    ('position', '💼 Должность'),
    ('object', '🏢 Объект'),
    ('object_address', '📍 Адрес объекта'),
    ('manager', '👤 Менеджер'),
    ('phone_main', '📞 Основной телефон'),
    ('phone_additional', '📞 Доп. телефон'),
    ('email', '📧 Email'),
    ('date', '📅 Дата рождения'),
]


def build_edit_keyboard(citizenship: str = '') -> InlineKeyboardMarkup:
    """
    Генерировать клавиатуру редактирования из конфига.

    Показывает базовые текстовые поля + документы для данной категории.
    """
    builder = InlineKeyboardBuilder()

    # Базовые текстовые поля
    for field_key, label in _BASE_FIELDS:
        builder.button(text=label, callback_data=f"edit_{field_key}")

    # Документы для категории
    if citizenship and citizenship in DOC_FLOWS:
        for doc in DOC_FLOWS[citizenship]:
            label = DOC_LABELS.get(doc.key, doc.key)
            builder.button(text=f"📎 {label}", callback_data=f"edit_{doc.key}")

    builder.button(text="✅ Готово", callback_data="edit_done")
    builder.adjust(2)
    return builder.as_markup()


# ─── Prompts для полей ───────────────────────────────────────────────

_FIELD_PROMPTS = {
    'name': "Введите исправленное ФИО:",
    'citizenship': "Введите категорию (Патент/Студент/ЕАЭС/РВП/ВНЖ/Россия):",
    'gender': "Введите пол (Мужской/Женский):",
    'position': "Введите должность:",
    'object': "Введите объект:",
    'object_address': "Введите адрес объекта:",
    'manager': "Введите ФИО менеджера:",
    'phone_main': "Введите основной телефон:",
    'phone_additional': "Введите доп. телефон (или 'пропустить'):",
    'email': "Введите email:",
    'date': "Введите дату рождения (ДД.ММ.ГГГГ):",
    'registration': "Введите регистрацию:",
    'marital_status': "Введите семейное положение:",
}


def get_field_prompt(field: str) -> str:
    """Получить текст запроса для текстового поля."""
    if field in _FIELD_PROMPTS:
        return _FIELD_PROMPTS[field]
    # Для документов — подсказка из конфига
    label = DOC_LABELS.get(field, field)
    return f"Отправьте исправленный файл: {label}"


# ─── Валидация файлов ────────────────────────────────────────────────

def validate_file_extension(file_path: str) -> bool:
    """Проверить расширение файла по единому списку из config."""
    import os
    from config import ALLOWED_EXTENSIONS
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ALLOWED_EXTENSIONS
