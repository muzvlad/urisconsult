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
from config.documents import DOC_FLOWS, DOC_LABELS, get_doc_flow
from handlers.registration import WorkerForm
from services import db

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
    """Обработчик команды /start и кнопки.

    Проверяет, есть ли отклонённая анкета у пользователя.
    """
    await state.clear()
    cleanup_user_temp_files(message.from_user.id)

    # Ищем отклонённую анкету пользователя
    telegram_id = message.from_user.id
    rejected = await _find_rejected_worker(telegram_id)

    if rejected:
        # Есть отклонённая анкета — предлагаем исправить
        reasons = rejected.get('rejection_reasons', '[]')
        if isinstance(reasons, str):
            try:
                reasons = json.loads(reasons)
            except (json.JSONDecodeError, TypeError):
                reasons = []

        reasons_text = '\n'.join(
            f"  • {DOC_LABELS.get(r, r)}" for r in reasons
        )

        await message.answer(
            f"📋 У вас есть отклонённая анкета #{rejected['id']}.\n\n"
            f"Необходимо исправить:\n{reasons_text}\n\n"
            f"Хотите исправить? (нажмите 'Исправить анкету' или 'Новая анкета')",
            reply_markup=_get_fix_keyboard()
        )
        await state.set_state(WorkerForm.fix_choice)
        await state.update_data(
            rejected_worker_id=rejected['id'],
            rejection_reasons=reasons
        )
    else:
        # Обычная регистрация
        await message.answer(
            "👋 Здравствуйте! Я бот для заполнения анкет работников.\n\n"
            "Я помогу вам собрать всю необходимую информацию и сохранить её в правильном формате."
        )
        await message.answer(
            "📝 Введите ваше ФИО полностью (например: Иванов Иван Иванович):"
        )
        await state.set_state(WorkerForm.name)


def _get_fix_keyboard():
    """Клавиатура для выбора: исправить или новая анкета."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Исправить анкету")],
            [KeyboardButton(text="📝 Новая анкета")],
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
        "❌ Заполнение анкеты отменено.\n"
        "Чтобы начать заново, нажмите кнопку ниже:",
        reply_markup=get_start_keyboard()
    )


async def process_fix_choice(message: types.Message, state: FSMContext):
    """Обработка выбора: исправить или новая анкета."""
    data = await state.get_data()
    rejected_worker_id = data.get('rejected_worker_id')
    reasons = data.get('rejection_reasons', [])

    if message.text == "✏️ Исправить анкету":
        # Начинаем исправление — запрашиваем только отклонённые поля
        await message.answer(
            "✏️ Начинаем исправление анкеты.\n"
            "Будет предложено исправить только отклонённые поля.",
            reply_markup=types.ReplyKeyboardRemove()
        )

        # Сохраняем данные отклонённой анкеты в state
        worker = await db.get_worker(rejected_worker_id)
        if worker:
            await state.update_data(**{
                k: worker.get(k) for k in [
                    'name', 'citizenship', 'gender', 'position', 'object',
                    'object_address', 'manager', 'phone_main', 'phone_additional',
                    'email', 'date', 'registration',
                ]
            })
            await state.update_data(editing_rejected=True, rejection_reasons=reasons)

        # Начинаем с первого отклонённого поля
        if reasons:
            first_field = reasons[0]
            await _ask_rejected_field(message, state, first_field, reasons, 0)
        else:
            await message.answer("📝 Введите ваше ФИО:")
            await state.set_state(WorkerForm.name)

    elif message.text == "📝 Новая анкета":
        # Сбрасываем статус на pending и начинаем заново
        await db.resubmit_worker(rejected_worker_id)
        await state.clear()
        await message.answer(
            "📝 Начинаем заполнение новой анкеты.\n"
            "Введите ваше ФИО полностью:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(WorkerForm.name)

    else:
        await message.answer("Пожалуйста, выберите действие:",
                             reply_markup=_get_fix_keyboard())


async def _ask_rejected_field(message, state, field, reasons, index):
    """Запросить исправление конкретного отклонённого поля."""
    from keyboards.reply_kb import get_skip_keyboard, get_gender_keyboard
    from keyboards.inline_kb import get_citizenship_keyboard

    field_prompts = {
        'name': "📝 Введите исправленное ФИО:",
        'citizenship': "🌍 Выберите категорию:",
        'gender': "⚥ Выберите ваш пол:",
        'position': "💼 Введите должность:",
        'object': "🏢 Введите объект:",
        'object_address': "📍 Введите адрес объекта:",
        'manager': "👤 Введите ФИО менеджера:",
        'phone_main': "📞 Введите основной телефон:",
        'phone_additional': "📞 Введите доп. телефон (или 'пропустить'):",
        'email': "📧 Введите email:",
        'date': "📅 Введите дату рождения (ДД.ММ.ГГГГ):",
        'registration': "📋 Введите регистрацию:",
    }

    # Для документов
    doc_states = {
        'photo': WorkerForm.photo,
        'passport': WorkerForm.passport,
    }
    for cat_docs in DOC_FLOWS.values():
        for doc in cat_docs:
            if doc.key not in doc_states:
                doc_states[doc.key] = getattr(WorkerForm, doc.key, None)

    # Пропуск если не текстовые поля
    skip_fields = {'photo', 'passport'}
    skip_fields.update({d.key for docs in DOC_FLOWS.values() for d in docs})

    if field in skip_fields and field not in field_prompts:
        # Документ — запрашиваем отправку файла
        doc_label = DOC_LABELS.get(field, field)
        prompt = f"📎 Отправьте исправленный файл: {doc_label}"
        await message.answer(prompt, reply_markup=get_skip_keyboard())
        state_obj = doc_states.get(field)
        if state_obj:
            await state.set_state(state_obj)
            await state.update_data(
                fix_current_field=field,
                fix_reasons=reasons,
                fix_index=index
            )
        return

    # Текстовое поле
    prompt = field_prompts.get(field, f"Введите значение для {field}:")
    await message.answer(prompt)

    # Устанавливаем правильную клавиатуру
    if field == 'citizenship':
        await message.answer("🌍 Выберите категорию:",
                             reply_markup=get_citizenship_keyboard())
        await state.set_state(WorkerForm.citizenship)
    elif field == 'gender':
        await message.answer("⚥ Выберите пол:",
                             reply_markup=get_gender_keyboard())
        await state.set_state(WorkerForm.gender)
    elif field == 'phone_additional':
        await state.set_state(WorkerForm.phone_additional)
    elif field in WorkerForm.__dict__:
        state_obj = getattr(WorkerForm, field, None)
        if state_obj:
            await state.set_state(state_obj)

    await state.update_data(
        fix_current_field=field,
        fix_reasons=reasons,
        fix_index=index
    )


async def process_fix_value(message: types.Message, state: FSMContext):
    """Обработка исправленного значения."""
    data = await state.get_data()
    field = data.get('fix_current_field')
    reasons = data.get('fix_reasons', [])
    index = data.get('fix_index', 0)

    # Сохраняем исправленное значение
    await state.update_data(**{field: message.text.strip()})

    # Следующее поле
    next_index = index + 1
    if next_index < len(reasons):
        next_field = reasons[next_index]
        await _ask_rejected_field(message, state, next_field, reasons, next_index)
    else:
        # Все поля исправлены — показываем подтверждение
        from handlers.confirmation import show_confirmation
        await message.answer("✅ Все замечания исправлены!",
                             reply_markup=types.ReplyKeyboardRemove())
        await show_confirmation(message, state)


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

    # Обработка выбора исправления
    dp.message.register(process_fix_choice, form_class.fix_choice)

    # Обработка исправленных значений (текстовые поля)
    dp.message.register(process_fix_value, form_class.fix_value)

    dp.message.register(any_message, default_state, F.text)
