"""
Инлайн клавиатуры
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_citizenship_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора гражданства"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Россия",
        callback_data="citizenship_Россия"
    )
    builder.button(
        text="ЕАЭС",
        callback_data="citizenship_ЕАЭС"
    )
    builder.button(
        text="У меня патент",
        callback_data="citizenship_Патент"
    )
    builder.button(
        text="Студент",
        callback_data="citizenship_Студент"
    )
    builder.button(
        text="РВП",
        callback_data="citizenship_РВП"
    )
    builder.button(
        text="ВНЖ",
        callback_data="citizenship_ВНЖ"
    )
    builder.adjust(1)
    return builder.as_markup()
