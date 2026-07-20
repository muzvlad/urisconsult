"""
Обработчики команд

Включает:
- /start — начало регистрации (или исправления отклонённой анкеты)
- /cancel — отмена
- Обработка отклонённых анкет
"""
import os
import glob
import json
import logging
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import DOCS_DIR
from config.documents import DOC_FLOWS, DOC_LABELS, FIELD_LABELS, get_doc_flow
from handlers.registration import get_worker_form
from services import db
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_document_state, get_all_doc_keys, get_field_prompt

logger = logging.getLogger(__name__)


# ─── Inline callback для отклонённых анкет ───────────────────────────

async def handle_rejected_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка inline кнопок из уведомления об отклонении."""
    await callback.answer()

    data = callback.data
    worker_id = data.split(":")[1]

    if data.startswith("fix_rejected:"):
        worker = await db.get_worker(worker_id)
        if not worker:
            await callback.message.answer("Анкета не найдена.")
            return

        reasons = worker.get('rejection_reasons', '[]')
        if isinstance(reasons, str):
            try:
                reasons = json.loads(reasons)
            except (json.JSONDecodeError, TypeError):
                reasons = []

        await callback.message.edit_text(
            "Начинаем исправление анкеты.\n"
            "Будет предложено исправить только отклонённые поля.",
        )

        worker_data = {'id': worker_id}
        for k in ['name', 'citizenship', 'gender', 'position', 'object',
                   'object_address', 'manager', 'phone_main', 'phone_additional',
                   'email', 'date', 'registration']:
            worker_data[k] = worker.get(k)
        await state.update_data(**worker_data)
        await state.update_data(editing_rejected=True, rejection_reasons=reasons)

        if reasons:
            await _ask_rejected_field(callback.message, state, reasons[0], reasons, 0)
        else:
            await callback.message.answer("Введите ваше ФИО:")
            await state.set_state(get_worker_form().name)

    elif data.startswith("new_rejected:"):
        await db.resubmit_worker(worker_id)
        await state.clear()
        await callback.message.edit_text(
            "Начинаем заполнение новой анкеты.\n"
            "Введите ваше ФИО полностью:",
        )
        await state.set_state(get_worker_form().name)


def get_start_keyboard():
    """Клавиатура с кнопкой Start"""
    button = KeyboardButton(text="Начать регистрацию")
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
    """Обработчик команды /start и кнопки."""
    await state.clear()
    cleanup_user_temp_files(message.from_user.id)

    telegram_id = message.from_user.id
    rejected = await _find_rejected_worker(telegram_id)

    if rejected:
        reasons = rejected.get('rejection_reasons', '[]')
        if isinstance(reasons, str):
            try:
                reasons = json.loads(reasons)
            except (json.JSONDecodeError, TypeError):
                reasons = []

        reasons_text = '\n'.join(
            f"  {FIELD_LABELS.get(r, r)}" for r in reasons
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Исправить анкету",
                                     callback_data=f"fix_rejected:{rejected['id']}"),
                InlineKeyboardButton(text="Новая анкета",
                                     callback_data=f"new_rejected:{rejected['id']}"),
            ]
        ])

        await message.answer(
            f"У вас есть отклонённая анкета #{rejected['id']}.\n\n"
            f"Необходимо исправить:\n{reasons_text}",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "Здравствуйте! Я бот для заполнения анкет работников.\n\n"
            "Помогу собрать информацию и сохранить её в правильном формате."
        )
        await message.answer("Введите ваше ФИО полностью (например: Иванов Иван Иванович):")
        await state.set_state(get_worker_form().name)


def _get_fix_keyboard():
    """Клавиатура для выбора: исправить или новая анкета."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Исправить анкету")],
            [KeyboardButton(text="Новая анкета")],
        ],
        resize_keyboard=True
    )


async def _find_rejected_worker(telegram_id: int) -> dict | None:
    """Найти отклонённую анкету по telegram_id."""
    db_conn = await db.get_db()
    cursor = await db_conn.execute(
        "SELECT * FROM workers WHERE telegram_id = ? AND status = 'rejected' LIMIT 1",
        (telegram_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def cmd_cancel(message: types.Message, state: FSMContext):
    """Обработчик команды /cancel"""
    await state.clear()
    cleanup_user_temp_files(message.from_user.id)
    await message.answer(
        "Заполнение анкеты отменено.\nЧтобы начать заново, нажмите кнопку ниже:",
        reply_markup=get_start_keyboard()
    )


async def process_fix_choice(message: types.Message, state: FSMContext):
    """Обработка выбора: исправить или новая анкета."""
    data = await state.get_data()
    rejected_worker_id = data.get('rejected_worker_id')
    reasons = data.get('rejection_reasons', [])

    if message.text == "Исправить анкету":
        await message.answer(
            "Начинаем исправление анкеты.\n"
            "Будет предложено исправить только отклонённые поля.",
            reply_markup=types.ReplyKeyboardRemove()
        )

        worker = await db.get_worker(rejected_worker_id)
        if worker:
            worker_data = {}
            for k in ['name', 'citizenship', 'gender', 'position', 'object',
                       'object_address', 'manager', 'phone_main', 'phone_additional',
                       'email', 'date', 'registration']:
                worker_data[k] = worker.get(k)
            await state.update_data(**worker_data)
            await state.update_data(editing_rejected=True, rejection_reasons=reasons)

        if reasons:
            await _ask_rejected_field(message, state, reasons[0], reasons, 0)
        else:
            await message.answer("Введите ваше ФИО:")
            await state.set_state(get_worker_form().name)

    elif message.text == "Новая анкета":
        await db.resubmit_worker(rejected_worker_id)
        await state.clear()
        await message.answer(
            "Начинаем заполнение новой анкеты.\nВведите ваше ФИО полностью:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(get_worker_form().name)

    else:
        await message.answer("Пожалуйста, выберите действие:",
                             reply_markup=_get_fix_keyboard())


# ─── Все текстовые поля в режиме исправления ловятся здесь ───────────

async def process_fix_value(message: types.Message, state: FSMContext):
    """Обработка исправленного значения (текстовые поля)."""
    data = await state.get_data()
    field = data.get('fix_current_field')
    reasons = data.get('fix_reasons', [])
    index = data.get('fix_index', 0)

    if not field:
        return

    # Сохраняем исправленное значение
    await state.update_data(**{field: message.text.strip()})

    # Следующее поле
    next_index = index + 1
    if next_index < len(reasons):
        next_field = reasons[next_index]
        await _ask_rejected_field(message, state, next_field, reasons, next_index)
    else:
        from handlers.confirmation import show_confirmation
        await message.answer("Все замечания исправлены!",
                             reply_markup=types.ReplyKeyboardRemove())
        await show_confirmation(message, state)


async def any_message(message: types.Message):
    """Ответ на любое сообщение, когда бот не в состоянии"""
    await message.answer(
        "Для начала работы нажмите кнопку ниже",
        reply_markup=get_start_keyboard()
    )


async def _ask_rejected_field(message, state, field, reasons, index):
    """Запросить исправление конкретного отклонённого поля."""
    from keyboards.reply_kb import get_skip_keyboard

    all_doc_keys = get_all_doc_keys()

    if field in all_doc_keys:
        # Документ — запрашиваем отправку файла
        doc_label = DOC_LABELS.get(field, field)
        await message.answer(f"Отправьте исправленный файл: {doc_label}",
                             reply_markup=get_skip_keyboard())
        state_obj = get_document_state(field)
        if state_obj:
            await state.set_state(state_obj)
        else:
            logger.error("Не найдено состояние для документа: %s", field)
            await message.answer("❌ Ошибка. Пропустите этот документ.")
        await state.update_data(
            fix_current_field=field,
            fix_reasons=reasons,
            fix_index=index
        )
        return

    # Текстовое поле — ВСЕГДА fix_value
    prompt = get_field_prompt(field)
    await message.answer(prompt)

    await state.set_state(get_worker_form().fix_value)
    await state.update_data(
        fix_current_field=field,
        fix_reasons=reasons,
        fix_index=index
    )


def register_commands(dp, form_class):
    """Регистрация обработчиков команд"""
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_start, lambda message: message.text == "Начать регистрацию")
    dp.message.register(cmd_cancel, Command("cancel"))

    # Inline кнопки из уведомлений об отклонении
    dp.callback_query.register(handle_rejected_callback,
                               F.data.startswith("fix_rejected:"))
    dp.callback_query.register(handle_rejected_callback,
                               F.data.startswith("new_rejected:"))

    # Обработка выбора исправления
    dp.message.register(process_fix_choice, form_class.fix_choice)

    # Обработка исправленных значений — ТОЛЬКО fix_value
    dp.message.register(process_fix_value, form_class.fix_value)

    dp.message.register(any_message, default_state, F.text)
