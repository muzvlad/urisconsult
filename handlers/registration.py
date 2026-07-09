"""
Обработчики регистрации (FSM состояния)
"""
import re
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from keyboards.reply_kb import get_gender_keyboard, get_skip_keyboard, get_cancel_keyboard
# Убираем импорт process_document отсюда

logger = logging.getLogger(__name__)

# Состояния для FSM
class WorkerForm(StatesGroup):
    # Основная информация
    name = State()
    citizenship = State()
    gender = State()
    position = State()
    object = State()
    object_address = State()
    manager = State()
    phone_main = State()
    phone_additional = State()
    email = State()
    date = State()
    
    # Документы
    photo = State()
    passport = State()
    patent = State()
    registration = State()
    
    # Подтверждение
    confirmation = State()
    edit = State()

# Валидаторы
def validate_phone(phone: str) -> bool:
    """Любой непустой ввод допустим"""
    return bool(phone.strip())

def validate_email(email: str) -> bool:
    """Проверка формата email"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def validate_date(date: str) -> bool:
    """Проверка формата даты"""
    date_pattern = r'^\d{2}\.\d{2}\.\d{4}$'
    return bool(re.match(date_pattern, date))

# Обработчики состояний
async def process_name(message: types.Message, state: FSMContext):
    """Обработка ФИО"""
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer("❌ Пожалуйста, введите ФИО полностью (минимум 2 слова)")
        return
    
    await state.update_data(name=name)
    await message.answer("🌍 Введите ваше гражданство:")
    await state.set_state(WorkerForm.citizenship)

async def process_citizenship(message: types.Message, state: FSMContext):
    """Обработка гражданства"""
    await state.update_data(citizenship=message.text.strip())
    await message.answer("⚥ Выберите ваш пол:", reply_markup=get_gender_keyboard())
    await state.set_state(WorkerForm.gender)

async def process_gender(message: types.Message, state: FSMContext):
    """Обработка пола"""
    gender = message.text.strip()
    if gender not in ["Мужской", "Женский"]:
        await message.answer("❌ Пожалуйста, выберите пол из клавиатуры", reply_markup=get_gender_keyboard())
        return
    
    await state.update_data(gender=gender)
    await message.answer("💼 Введите вашу должность:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(WorkerForm.position)

async def process_position(message: types.Message, state: FSMContext):
    """Обработка должности"""
    await state.update_data(position=message.text.strip())
    await message.answer("🏢 Введите название объекта/компании:")
    await state.set_state(WorkerForm.object)

async def process_object(message: types.Message, state: FSMContext):
    """Обработка объекта"""
    await state.update_data(object=message.text.strip())
    await message.answer("📍 Введите адрес объекта:")
    await state.set_state(WorkerForm.object_address)

async def process_object_address(message: types.Message, state: FSMContext):
    """Обработка адреса объекта"""
    await state.update_data(object_address=message.text.strip())
    await message.answer("👤 Введите ФИО вашего менеджера/руководителя:")
    await state.set_state(WorkerForm.manager)

async def process_manager(message: types.Message, state: FSMContext):
    """Обработка менеджера"""
    await state.update_data(manager=message.text.strip())
    await message.answer(
        "📞 Введите основной номер телефона (в формате +79999999999):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(WorkerForm.phone_main)

async def process_phone_main(message: types.Message, state: FSMContext):
    """Обработка основного телефона"""
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
    await state.set_state(WorkerForm.phone_additional)

async def process_phone_additional(message: types.Message, state: FSMContext):
    """Обработка дополнительного телефона"""
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
    await message.answer("📧 Введите ваш email:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(WorkerForm.email)

async def process_email(message: types.Message, state: FSMContext):
    """Обработка email"""
    email = message.text.strip()
    if not validate_email(email):
        await message.answer("❌ Пожалуйста, введите корректный email (пример: name@domain.com)")
        return
    
    await state.update_data(email=email)
    await message.answer("📅 Введите дату рождения (в формате ДД.ММ.ГГГГ):")
    await state.set_state(WorkerForm.date)

async def process_date(message: types.Message, state: FSMContext):
    """Обработка даты рождения"""
    date = message.text.strip()
    if not validate_date(date):
        await message.answer("❌ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ")
        return
    
    await state.update_data(date=date)
    await message.answer(
        "📸 Отправьте ваше фото (селфи). Это может быть файл изображения.\n"
        "Или нажмите 'Пропустить':",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(WorkerForm.photo)

async def process_skip_to_documents(message: types.Message, state: FSMContext, doc_type: str, next_state):
    """Обработка пропуска документа"""
    if message.text == "⏭ Пропустить":
        await state.update_data({doc_type: None})
        
        # Определяем следующее состояние
        if doc_type == 'photo':
            await message.answer("📄 Отправьте скан паспорта (или 'пропустить'):")
            await state.set_state(WorkerForm.passport)
        elif doc_type == 'passport':
            await message.answer("📄 Отправьте скан патента (или 'пропустить'):")
            await state.set_state(WorkerForm.patent)
        elif doc_type == 'patent':
            await message.answer("📄 Отправьте скан регистрации (или 'пропустить'):")
            await state.set_state(WorkerForm.registration)
        return True
    return False

def register_registration_handlers(dp, form_class):
    """Регистрация обработчиков регистрации"""
    dp.message.register(process_name, form_class.name)
    dp.message.register(process_citizenship, form_class.citizenship)
    dp.message.register(process_gender, form_class.gender)
    dp.message.register(process_position, form_class.position)
    dp.message.register(process_object, form_class.object)
    dp.message.register(process_object_address, form_class.object_address)
    dp.message.register(process_manager, form_class.manager)
    dp.message.register(process_phone_main, form_class.phone_main)
    dp.message.register(process_phone_additional, form_class.phone_additional)
    dp.message.register(process_email, form_class.email)
    dp.message.register(process_date, form_class.date)

    dp.message.register(
        lambda message, state: process_skip_to_documents(message, state, 'photo', form_class.passport),
        form_class.photo, F.text == "⏭ Пропустить"
    )
    dp.message.register(
        lambda message, state: process_skip_to_documents(message, state, 'passport', form_class.patent),
        form_class.passport, F.text == "⏭ Пропустить"
    )
    dp.message.register(
        lambda message, state: process_skip_to_documents(message, state, 'patent', form_class.registration),
        form_class.patent, F.text == "⏭ Пропустить"
    )