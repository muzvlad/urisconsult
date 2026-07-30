"""
Обработчики регистрации (FSM состояния).

FSM генерируется динамически из config.documents — добавление нового типа
документа требует правки ТОЛЬКО в documents.py.
"""
import re
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from config.documents import DOC_FLOWS, get_doc_flow
from keyboards.reply_kb import (
    get_gender_keyboard, get_skip_keyboard, get_cancel_keyboard,
    get_marital_keyboard, get_add_relative_keyboard,
)
from keyboards.inline_kb import get_citizenship_keyboard

logger = logging.getLogger(__name__)


# ─── Динамическое создание FSM ─────────────────────────────────────

def _build_worker_form() -> type:
    """Динамически создаёт StatesGroup с состояниями для всех документов."""
    # Базовые состояния (личные данные)
    states = {
        'name', 'citizenship', 'gender',         'position', 'object',
        'object_address', 'manager', 'phone_main', 'phone_additional',
        'date',
        'russia_marital_status', 'russia_relatives', 'russia_relatives_phone',
        'confirmation', 'edit',
        'fix_choice', 'fix_value',
    }

    # Добавляем состояния для документов из конфига
    for cat_docs in DOC_FLOWS.values():
        for doc in cat_docs:
            states.add(doc.key)

    # Создаём класс динамически
    state_attrs = {s: State() for s in states}
    return type('WorkerForm', (StatesGroup,), state_attrs)


_worker_form: type[StatesGroup] | None = None


def get_worker_form() -> type[StatesGroup]:
    """Получить WorkerForm (ленивая инициализация)."""
    global _worker_form
    if _worker_form is None:
        _worker_form = _build_worker_form()
    return _worker_form


# ─── Валидаторы ─────────────────────────────────────────────────────

def validate_phone(phone: str) -> bool:
    """Валидация телефона: минимум 10 цифр."""
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10


def validate_email(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def validate_date(date: str) -> bool:
    """Валидация даты: формат ДД.ММ.ГГГГ + реальная проверка через datetime."""
    from datetime import datetime
    date_pattern = r'^(\d{2})\.(\d{2})\.(\d{4})$'
    match = re.match(date_pattern, date)
    if not match:
        return False
    try:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        datetime(year, month, day)
        return True
    except ValueError:
        return False


# ─── Обработчики состояний ──────────────────────────────────────────

async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer("❌ Пожалуйста, введите ФИО полностью (минимум 2 слова)")
        return
    if not all(c.isalpha() or c.isspace() or c == '-' for c in name):
        await message.answer("❌ ФИО должно содержать только буквы, пробелы и дефис")
        return
    await state.update_data(name=name)
    await message.answer(
        "🌍 Выберите категорию:",
        reply_markup=get_citizenship_keyboard()
    )
    await state.set_state(get_worker_form().citizenship)


async def process_citizenship_callback(callback: types.CallbackQuery, state: FSMContext):
    citizenship = callback.data.replace("citizenship_", "")
    await state.update_data(citizenship=citizenship)
    await callback.message.edit_text(f"🌍 **Категория:** {citizenship}")
    await callback.message.answer("⚥ Выберите ваш пол:", reply_markup=get_gender_keyboard())
    await state.set_state(get_worker_form().gender)
    await callback.answer()


async def process_gender(message: types.Message, state: FSMContext):
    gender = message.text.strip()
    if gender not in ["Мужской", "Женский"]:
        await message.answer("❌ Пожалуйста, выберите пол из клавиатуры", reply_markup=get_gender_keyboard())
        return
    await state.update_data(gender=gender)
    await message.answer("💼 Введите вашу должность:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(get_worker_form().position)


async def process_position(message: types.Message, state: FSMContext):
    await state.update_data(position=message.text.strip())
    await message.answer("🏢 Введите название объекта/компании:")
    await state.set_state(get_worker_form().object)


async def process_object(message: types.Message, state: FSMContext):
    await state.update_data(object=message.text.strip())
    await message.answer("📍 Введите адрес объекта:")
    await state.set_state(get_worker_form().object_address)


async def process_object_address(message: types.Message, state: FSMContext):
    await state.update_data(object_address=message.text.strip())
    await message.answer("👤 Введите ФИО вашего менеджера/руководителя:")
    await state.set_state(get_worker_form().manager)


async def process_manager(message: types.Message, state: FSMContext):
    await state.update_data(manager=message.text.strip())
    await message.answer(
        "📞 Введите основной номер телефона (в формате +79999999999):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(get_worker_form().phone_main)


async def process_phone_main(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заполнение отменено. Для начала отправьте /start")
        return
    phone = message.text.strip()
    if not validate_phone(phone):
        await message.answer("❌ Пожалуйста, введите номер телефона")
        return
    await state.update_data(phone_main=phone)
    await message.answer(
        "📞 Введите дополнительный номер телефона (или отправьте 'пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(get_worker_form().phone_additional)


async def process_phone_additional(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заполнение отменено. Для начала отправьте /start")
        return
    phone = message.text.strip()
    if phone == "⏭ Пропустить":
        phone = "Не указан"
    elif phone and not validate_phone(phone):
        await message.answer("❌ Пожалуйста, введите номер телефона или нажмите 'Пропустить'")
        return
    await state.update_data(phone_additional=phone)
    await message.answer("📅 Введите дату рождения (в формате ДД.ММ.ГГГГ):")
    await state.set_state(get_worker_form().date)


async def process_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    if not validate_email(email):
        await message.answer("❌ Пожалуйста, введите корректный email (пример: name@domain.com)")
        return
    await state.update_data(email=email)
    await message.answer("📅 Введите дату рождения (в формате ДД.ММ.ГГГГ):")
    await state.set_state(get_worker_form().date)


async def process_date(message: types.Message, state: FSMContext):
    date = message.text.strip()
    if not validate_date(date):
        await message.answer("❌ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ")
        return
    await state.update_data(date=date)

    # Переходим к первому документу из потока
    data = await state.get_data()
    citizenship = data.get('citizenship')
    if not citizenship:
        await message.answer("❌ Ошибка: категория не выбрана. Начните заново.")
        await state.clear()
        return

    flow = get_doc_flow(citizenship)
    if not flow:
        await message.answer("❌ Ошибка: неизвестная категория. Начните заново.")
        await state.clear()
        return

    first_doc = flow[0]  # Первый документ (обычно photo)

    from config.documents import DOC_PROMPTS
    skip_text = "\nИли нажмите 'Пропустить'" if first_doc.can_skip else ""
    await message.answer(
        DOC_PROMPTS.get(first_doc.key, f"Отправьте {first_doc.label}:") + skip_text,
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(getattr(get_worker_form(), first_doc.key))


# ─── Дополнительные поля для России ─────────────────────────────────

async def process_russia_marital_status(message: types.Message, state: FSMContext):
    marital = message.text.strip()
    valid_options = ["Не женат/Не замужем", "Женат/Замужем", "Разведен/Разведена", "Вдовец/Вдова"]
    if marital not in valid_options:
        await message.answer("❌ Пожалуйста, выберите семейное положение из клавиатуры",
                             reply_markup=get_marital_keyboard())
        return
    await state.update_data(russia_marital_status=marital)
    await message.answer(
        "👨‍👩‍👧‍👦 Введите данные ближайшего родственника:\n"
        "ФИО, Год рождения, Телефон\n"
        "(например: Иванов Иван Иванович, 1985, +79991234567)\n\n"
        "Или нажмите 'Готово' если родственников добавлять не нужно:",
        reply_markup=get_add_relative_keyboard()
    )
    await state.set_state(get_worker_form().russia_relatives)


async def process_russia_relatives(message: types.Message, state: FSMContext):
    if message.text == "✅ Готово":
        data = await state.get_data()
        relatives = data.get('russia_relatives_list', [])
        if relatives:
            await message.answer(
                f"✅ Добавлено родственников: {len(relatives)}\n"
                "Все документы получены!",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await message.answer("✅ Все документы получены!", reply_markup=ReplyKeyboardRemove())

        from handlers.confirmation import show_confirmation
        await show_confirmation(message, state)
        return

    if message.text == "➕ Добавить родственника":
        await message.answer(
            "👨‍👩‍👧‍👦 Введите данные родственника:\n"
            "ФИО, Год рождения, Телефон\n"
            "(например: Иванов Иван Иванович, 1985, +79991234567)"
        )
        return

    parts = [p.strip() for p in message.text.split(',')]
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат. Введите:\n"
            "ФИО, Год рождения, Телефон\n"
            "(например: Иванов Иван Иванович, 1985, +79991234567)"
        )
        return

    data = await state.get_data()
    relatives = data.get('russia_relatives_list', [])
    relatives.append({
        'name': parts[0],
        'birth_year': parts[1],
        'phone': parts[2],
    })
    await state.update_data(russia_relatives_list=relatives)

    await message.answer(
        f"✅ Родственник добавлен: {parts[0]}\n\n"
        f"Всего родственников: {len(relatives)}\n\n"
        "Добавьте еще или нажмите 'Готово':",
        reply_markup=get_add_relative_keyboard()
    )


# ─── Регистрация обработчиков ──────────────────────────────────────

def register_registration_handlers(dp, form_class):
    """Регистрация обработчиков регистрации."""
    dp.message.register(process_name, form_class.name)
    dp.callback_query.register(process_citizenship_callback, form_class.citizenship,
                               F.data.startswith("citizenship_"))
    dp.message.register(process_gender, form_class.gender)
    dp.message.register(process_position, form_class.position)
    dp.message.register(process_object, form_class.object)
    dp.message.register(process_object_address, form_class.object_address)
    dp.message.register(process_manager, form_class.manager)
    dp.message.register(process_phone_main, form_class.phone_main)
    dp.message.register(process_phone_additional, form_class.phone_additional)
    dp.message.register(process_date, form_class.date)

    # Обработчики для России (доп. поля)
    dp.message.register(process_russia_marital_status, form_class.russia_marital_status)
    dp.message.register(process_russia_relatives, form_class.russia_relatives)
