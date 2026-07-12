"""
Обработчики команд
"""
import os
import glob
import logging
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import DOCS_DIR
from handlers.registration import WorkerForm

logger = logging.getLogger(__name__)

def get_start_keyboard():
    """Клавиатура с кнопкой Start"""
    button = KeyboardButton(text="🚀 Начать регистрацию")
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[button]],
        resize_keyboard=True
    )
    return keyboard

def cleanup_user_temp_files(user_id: int):
    """Удалить временные файлы пользователя"""
    for f in glob.glob(os.path.join(DOCS_DIR, f"temp_*_{user_id}.*")):
        try:
            os.remove(f)
        except OSError:
            pass

async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start и кнопки"""
    await state.clear()
    cleanup_user_temp_files(message.from_user.id)

    await message.answer(
        "👋 Здравствуйте! Я бот для заполнения анкет работников.\n\n"
        "Я помогу вам собрать всю необходимую информацию и сохранить её в правильном формате."
    )
    await message.answer(
        "📝 Введите ваше ФИО полностью (например: Иванов Иван Иванович):"
    )
    await state.set_state(WorkerForm.name)

async def cmd_cancel(message: types.Message, state: FSMContext):
    """Обработчик команды /cancel"""
    await state.clear()
    cleanup_user_temp_files(message.from_user.id)
    await message.answer(
        "❌ Заполнение анкеты отменено.\n"
        "Чтобы начать заново, нажмите кнопку ниже:",
        reply_markup=get_start_keyboard()
    )

async def any_message(message: types.Message):
    """Ответ на любое сообщение, когда бот не в состоянии"""
    await message.answer(
        "Для начала работы нажмите кнопку ⬇️",
        reply_markup=get_start_keyboard()
    )

def register_commands(dp, form_class):
    """Регистрация обработчиков команд"""
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_start, lambda message: message.text == "🚀 Начать регистрацию")
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(any_message, default_state, F.text)