"""
Клавиатуры для бота
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_gender_keyboard():
    """Клавиатура для выбора пола"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Мужской")
    builder.button(text="Женский")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_skip_keyboard():
    """Клавиатура с кнопкой пропустить"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭ Пропустить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_confirmation_keyboard():
    """Клавиатура для подтверждения"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm")
    builder.button(text="❌ Заполнить заново", callback_data="restart")
    builder.button(text="✏️ Исправить", callback_data="edit")
    builder.adjust(1)
    return builder.as_markup()

def get_edit_keyboard():
    """Клавиатура для выбора поля для исправления"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 ФИО", callback_data="edit_name")
    builder.button(text="🌍 Гражданство", callback_data="edit_citizenship")
    builder.button(text="⚥ Пол", callback_data="edit_gender")
    builder.button(text="💼 Должность", callback_data="edit_position")
    builder.button(text="🏢 Объект", callback_data="edit_object")
    builder.button(text="📍 Адрес объекта", callback_data="edit_object_address")
    builder.button(text="👤 Менеджер", callback_data="edit_manager")
    builder.button(text="📞 Основной телефон", callback_data="edit_phone_main")
    builder.button(text="📞 Доп. телефон", callback_data="edit_phone_additional")
    builder.button(text="📧 Email", callback_data="edit_email")
    builder.button(text="📅 Дата рождения", callback_data="edit_date")
    builder.button(text="📸 Фото", callback_data="edit_photo")
    builder.button(text="🪪 Паспорт", callback_data="edit_passport")
    builder.button(text="📄 Патент", callback_data="edit_patent")
    builder.button(text="📋 Регистрация", callback_data="edit_registration")
    builder.button(text="✅ Готово", callback_data="edit_done")
    builder.adjust(2)
    return builder.as_markup()