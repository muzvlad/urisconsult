"""
Обработчики регистрации (FSM состояния)
"""
import re
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from keyboards.reply_kb import get_gender_keyboard, get_skip_keyboard, get_cancel_keyboard, get_marital_keyboard, get_add_relative_keyboard
from keyboards.inline_kb import get_citizenship_keyboard
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
    
    # Документы (общие)
    photo = State()
    passport = State()
    
    # Документы для Патента
    patent_snils = State()
    patent_registration = State()
    patent_migration_card = State()
    patent_dms = State()
    patent_patent = State()
    patent_inn = State()
    patent_receipt = State()
    patent_language_cert = State()
    patent_bank_details = State()
    patent_fingerprint_card = State()
    
    # Документы для Студента
    student_snils = State()
    student_registration = State()
    student_migration_card = State()
    student_dms = State()
    student_inn = State()
    student_fingerprint_card = State()
    student_university_cert = State()
    student_bank_details = State()
    
    # Документы для ЕАЭС
    eaeas_registration = State()
    eaeas_migration_card = State()
    eaeas_dms = State()
    eaeas_inn = State()
    eaeas_snils = State()
    eaeas_fingerprint_card = State()
    eaeas_bank_details = State()
    
    # Документы для РВП
    rvp_migration_card = State()
    rvp_dms_oms = State()
    rvp_inn = State()
    rvp_snils = State()
    rvp_bank_details = State()
    
    # Документы для ВНЖ
    vnzh_migration_card = State()
    vnzh_vnzh = State()
    vnzh_dms_oms = State()
    vnzh_inn = State()
    vnzh_snils = State()
    vnzh_work_book = State()
    vnzh_bank_details = State()
    
    # Документы для России
    russia_passport_propiska = State()
    russia_propiska = State()
    russia_inn = State()
    russia_snils = State()
    russia_education_doc = State()
    russia_work_book = State()
    russia_military_doc = State()
    
    # Дополнительные поля для России (мужчины)
    russia_marital_status = State()
    russia_relatives = State()
    russia_relatives_phone = State()
    
    # Документы (продолжение)
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
    await message.answer(
        "🌍 Выберите категорию:",
        reply_markup=get_citizenship_keyboard()
    )
    await state.set_state(WorkerForm.citizenship)

async def process_citizenship_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора гражданства через инлайн-кнопку"""
    citizenship = callback.data.replace("citizenship_", "")
    await state.update_data(citizenship=citizenship)
    await callback.message.edit_text(f"🌍 **Категория:** {citizenship}")
    await callback.message.answer("⚥ Выберите ваш пол:", reply_markup=get_gender_keyboard())
    await state.set_state(WorkerForm.gender)
    await callback.answer()

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

async def skip_photo(message: types.Message, state: FSMContext):
    await process_skip_to_documents(message, state, 'photo', WorkerForm.passport)

async def skip_passport(message: types.Message, state: FSMContext):
    await process_skip_to_documents(message, state, 'passport', WorkerForm.patent)

async def skip_patent(message: types.Message, state: FSMContext):
    await process_skip_to_documents(message, state, 'patent', WorkerForm.registration)

# Обработчики для России (доп. поля)
async def process_russia_marital_status(message: types.Message, state: FSMContext):
    """Обработка семейного положения"""
    marital = message.text.strip()
    valid_options = ["Не женат/Не замужем", "Женат/Замужем", "Разведен/Разведена", "Вдовец/Вдова"]
    if marital not in valid_options:
        await message.answer("❌ Пожалуйста, выберите семейное положение из клавиатуры", reply_markup=get_marital_keyboard())
        return
    
    await state.update_data(russia_marital_status=marital)
    await message.answer(
        "👨‍👩‍👧‍👦 Введите данные ближайшего родственника:\n"
        "ФИО, Год рождения, Телефон\n"
        "(например: Иванов Иван Иванович, 1985, +79991234567)\n\n"
        "Или нажмите 'Готово' если родственников добавлять не нужно:",
        reply_markup=get_add_relative_keyboard()
    )
    await state.set_state(WorkerForm.russia_relatives)

async def process_russia_relatives(message: types.Message, state: FSMContext):
    """Обработка добавления родственника"""
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
    
    # Парсим данные родственника
    parts = [p.strip() for p in message.text.split(',')]
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат. Введите:\n"
            "ФИО, Год рождения, Телефон\n"
            "(например: Иванов Иван Иванович, 1985, +79991234567)"
        )
        return
    
    name = parts[0]
    birth_year = parts[1]
    phone = parts[2]
    
    data = await state.get_data()
    relatives = data.get('russia_relatives_list', [])
    relatives.append({
        'name': name,
        'birth_year': birth_year,
        'phone': phone
    })
    await state.update_data(russia_relatives_list=relatives)
    
    await message.answer(
        f"✅ Родственник добавлен: {name}\n\n"
        f"Всего родственников: {len(relatives)}\n\n"
        "Добавьте еще или нажмите 'Готово':",
        reply_markup=get_add_relative_keyboard()
    )

def register_registration_handlers(dp, form_class):
    """Регистрация обработчиков регистрации"""
    dp.message.register(process_name, form_class.name)
    dp.callback_query.register(process_citizenship_callback, form_class.citizenship, F.data.startswith("citizenship_"))
    dp.message.register(process_gender, form_class.gender)
    dp.message.register(process_position, form_class.position)
    dp.message.register(process_object, form_class.object)
    dp.message.register(process_object_address, form_class.object_address)
    dp.message.register(process_manager, form_class.manager)
    dp.message.register(process_phone_main, form_class.phone_main)
    dp.message.register(process_phone_additional, form_class.phone_additional)
    dp.message.register(process_email, form_class.email)
    dp.message.register(process_date, form_class.date)

    dp.message.register(skip_photo, form_class.photo, F.text == "⏭ Пропустить")
    dp.message.register(skip_passport, form_class.passport, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent, form_class.patent_patent, F.text == "⏭ Пропустить")
    
    # Обработчики для России (доп. поля)
    dp.message.register(process_russia_marital_status, form_class.russia_marital_status)
    dp.message.register(process_russia_relatives, form_class.russia_relatives)