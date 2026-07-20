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

def get_marital_keyboard():
    """Клавиатура для выбора семейного положения"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Не женат/Не замужем")
    builder.button(text="Женат/Замужем")
    builder.button(text="Разведен/Разведена")
    builder.button(text="Вдовец/Вдова")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_add_relative_keyboard():
    """Клавиатура для добавления родственника"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Добавить родственника")
    builder.button(text="✅ Готово")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_confirmation_keyboard():
    """Клавиатура для подтверждения"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm")
    builder.button(text="❌ Заполнить заново", callback_data="restart")
    builder.button(text="✏️ Исправить", callback_data="edit")
    builder.adjust(1)
    return builder.as_markup()