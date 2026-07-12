"""
Обработчики документов
"""
import os
import logging
from aiogram import types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config import DOCS_DIR, ALLOWED_EXTENSIONS
from services.file_saver import FileSaver
from keyboards.reply_kb import get_skip_keyboard, get_marital_keyboard, get_add_relative_keyboard
from handlers.registration import WorkerForm
from handlers.confirmation import show_confirmation

logger = logging.getLogger(__name__)

# Порядок документов для категории "Патент"
PATENT_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('patent_snils', '📄 Отправьте СНИЛС (или перевод паспорта):', WorkerForm.patent_snils, True),
    ('patent_registration', '📋 Отправьте регистрацию:', WorkerForm.patent_registration, False),
    ('patent_migration_card', '🎫 Отправьте миграционную карту:', WorkerForm.patent_migration_card, False),
    ('patent_dms', '🏥 Отправьте ДМС:', WorkerForm.patent_dms, False),
    ('patent_patent', '📝 Отправьте патент:', WorkerForm.patent_patent, False),
    ('patent_inn', '🔢 Отправьте ИНН (можно пропустить):', WorkerForm.patent_inn, True),
    ('patent_receipt', '🧾 Отправьте чек по патенту:', WorkerForm.patent_receipt, False),
    ('patent_language_cert', '🎓 Отправьте сертификат о знании языка:', WorkerForm.patent_language_cert, False),
    ('patent_bank_details', '💳 Отправьте реквизиты банковской карты:', WorkerForm.patent_bank_details, False),
    ('patent_fingerprint_card', '🖐 Отправьте дактилоскопическую карту:', WorkerForm.patent_fingerprint_card, False),
]

# Порядок документов для категории "Студент"
STUDENT_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('student_snils', '📄 Отправьте СНИЛС (или перевод паспорта):', WorkerForm.student_snils, True),
    ('student_registration', '📋 Отправьте регистрацию:', WorkerForm.student_registration, False),
    ('student_migration_card', '🎫 Отправьте миграционную карту:', WorkerForm.student_migration_card, False),
    ('student_dms', '🏥 Отправьте ДМС:', WorkerForm.student_dms, False),
    ('student_inn', '🔢 Отправьте ИНН:', WorkerForm.student_inn, False),
    ('student_fingerprint_card', '🖐 Отправьте дактилоскопическую карту:', WorkerForm.student_fingerprint_card, False),
    ('student_university_cert', '🎓 Отправьте справку из ВУЗа:', WorkerForm.student_university_cert, False),
    ('student_bank_details', '💳 Отправьте реквизиты счета банковской карты:', WorkerForm.student_bank_details, False),
]

# Порядок документов для категории "ЕАЭС"
EAEAS_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('eaeas_registration', '📋 Отправьте регистрацию:', WorkerForm.eaeas_registration, False),
    ('eaeas_migration_card', '🎫 Отправьте миграционную карту:', WorkerForm.eaeas_migration_card, False),
    ('eaeas_dms', '🏥 Отправьте ДМС:', WorkerForm.eaeas_dms, False),
    ('eaeas_inn', '🔢 Отправьте ИНН:', WorkerForm.eaeas_inn, False),
    ('eaeas_snils', '📄 Отправьте СНИЛС:', WorkerForm.eaeas_snils, False),
    ('eaeas_fingerprint_card', '🖐 Отправьте дактилоскопическую карту:', WorkerForm.eaeas_fingerprint_card, False),
    ('eaeas_bank_details', '💳 Отправьте реквизиты счета банковской карты:', WorkerForm.eaeas_bank_details, False),
]

# Порядок документов для категории "РВП"
RVP_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('rvp_migration_card', '🎫 Отправьте миграционную карту:', WorkerForm.rvp_migration_card, False),
    ('rvp_dms_oms', '🏥 Отправьте ДМС или ОМС:', WorkerForm.rvp_dms_oms, False),
    ('rvp_inn', '🔢 Отправьте ИНН:', WorkerForm.rvp_inn, False),
    ('rvp_snils', '📄 Отправьте СНИЛС:', WorkerForm.rvp_snils, False),
    ('rvp_bank_details', '💳 Отправьте реквизиты счета банковской карты:', WorkerForm.rvp_bank_details, False),
]

# Порядок документов для категории "ВНЖ"
VNZH_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('vnzh_migration_card', '🎫 Отправьте миграционную карту (желательно):', WorkerForm.vnzh_migration_card, True),
    ('vnzh_vnzh', '🪪 Отправьте ВНЖ:', WorkerForm.vnzh_vnzh, False),
    ('vnzh_dms_oms', '🏥 Отправьте ДМС или ОМС:', WorkerForm.vnzh_dms_oms, False),
    ('vnzh_inn', '🔢 Отправьте ИНН:', WorkerForm.vnzh_inn, False),
    ('vnzh_snils', '📄 Отправьте СНИЛС:', WorkerForm.vnzh_snils, False),
    ('vnzh_work_book', '📖 Отправьте трудовую книжку или ЭТК с Госуслуг:', WorkerForm.vnzh_work_book, False),
    ('vnzh_bank_details', '💳 Отправьте реквизиты счета банковской карты:', WorkerForm.vnzh_bank_details, False),
]

# Порядок документов для категории "Россия"
RUSSIA_DOC_FLOW = [
    ('photo', '📸 Отправьте фото (селфи):', WorkerForm.photo, False),
    ('passport', '🪪 Отправьте паспорт в развороте:', WorkerForm.passport, False),
    ('russia_passport_propiska', '📖 Отправьте паспорт (разворот прописки):', WorkerForm.russia_passport_propiska, False),
    ('russia_propiska', '📋 Отправьте прописку:', WorkerForm.russia_propiska, False),
    ('russia_inn', '🔢 Отправьте ИНН:', WorkerForm.russia_inn, False),
    ('russia_snils', '📄 Отправьте СНИЛС:', WorkerForm.russia_snils, False),
    ('russia_education_doc', '🎓 Отправьте документ об образовании (или пропустите):', WorkerForm.russia_education_doc, True),
    ('russia_work_book', '📖 Отправьте трудовую книжку или ЭТК с Госуслуг:', WorkerForm.russia_work_book, False),
    ('russia_military_doc', '🎖 Отправьте военный билет или приписное (или пропустите):', WorkerForm.russia_military_doc, True),
]

# Маппинг категорий на потоки документов
CITIZENSHIP_FLOWS = {
    'Патент': PATENT_DOC_FLOW,
    'Студент': STUDENT_DOC_FLOW,
    'ЕАЭС': EAEAS_DOC_FLOW,
    'РВП': RVP_DOC_FLOW,
    'ВНЖ': VNZH_DOC_FLOW,
    'Россия': RUSSIA_DOC_FLOW,
}


def _validate_extension(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _get_flow_for_citizenship(citizenship: str) -> list:
    """Получить поток документов для категории"""
    return CITIZENSHIP_FLOWS.get(citizenship, PATENT_DOC_FLOW)


def _get_next_doc(doc_type: str, flow: list):
    """Получить следующий документ в цепочке"""
    for i, item in enumerate(flow):
        if item[0] == doc_type:
            if i + 1 < len(flow):
                return flow[i + 1]
            return None
    return None


async def _download_document(message: types.Message, state: FSMContext, bot: Bot, doc_type: str) -> bool:
    """Скачать документ и перейти к следующему"""
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
        else:
            file_id = message.document.file_id

        file = await bot.get_file(file_id)
        file_path = file.file_path

        if not _validate_extension(file_path):
            await message.answer(
                f"❌ Недопустимый формат файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}\n"
                "Попробуйте еще раз или нажмите 'Пропустить':"
            )
            return False

        ext = os.path.splitext(file_path)[1] or '.jpg'
        data = await state.get_data()
        temp_path = os.path.join(DOCS_DIR, f"temp_{doc_type}_{message.from_user.id}{ext}")

        await bot.download_file(file_path, temp_path)

        temp_files = data.get('temp_files', [])
        temp_files.append(temp_path)
        await state.update_data(**{f'{doc_type}_temp_path': temp_path, 'temp_files': temp_files})

        # Определяем поток документов на основе гражданства
        citizenship = data.get('citizenship', 'Патент')
        flow = _get_flow_for_citizenship(citizenship)

        # Переходим к следующему документу
        next_item = _get_next_doc(doc_type, flow)
        if next_item:
            next_doc_type, next_prompt, next_state, can_skip = next_item
            skip_text = "\nИли нажмите 'Пропустить'" if can_skip else ""
            await message.answer(next_prompt + skip_text, reply_markup=get_skip_keyboard())
            await state.set_state(next_state)
        else:
            await message.answer("✅ Все документы получены!", reply_markup=ReplyKeyboardRemove())
            await _after_documents(message, state)

        return True
    except Exception as e:
        logger.error("Ошибка при загрузке %s: %s", doc_type, e)
        await message.answer("❌ Ошибка при загрузке. Попробуйте еще раз или нажмите 'Пропустить':")
        return False


async def _skip_document(message: types.Message, state: FSMContext, doc_type: str):
    """Пропустить документ и перейти к следующему"""
    await state.update_data({f'{doc_type}_temp_path': None})

    data = await state.get_data()
    citizenship = data.get('citizenship', 'Патент')
    flow = _get_flow_for_citizenship(citizenship)

    next_item = _get_next_doc(doc_type, flow)
    if next_item:
        next_doc_type, next_prompt, next_state, can_skip = next_item
        skip_text = "\nИли нажмите 'Пропустить'" if can_skip else ""
        await message.answer(next_prompt + skip_text, reply_markup=get_skip_keyboard())
        await state.set_state(next_state)
    else:
        await message.answer("✅ Все документы получены!", reply_markup=ReplyKeyboardRemove())
        await _after_documents(message, state)


async def _after_documents(message: types.Message, state: FSMContext):
    """Обработка после сбора документов (для России - доп. поля)"""
    data = await state.get_data()
    citizenship = data.get('citizenship', '')
    gender = data.get('gender', '')
    
    if citizenship == 'Россия' and gender == 'Мужской':
        await message.answer(
            "👨 Выберите ваше семейное положение:",
            reply_markup=get_marital_keyboard()
        )
        await state.set_state(WorkerForm.russia_marital_status)
    else:
        await show_confirmation(message, state)


# Обработчики для каждого документа
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'photo')

async def process_passport(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'passport')

# Патент
async def process_patent_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_snils')

async def process_patent_registration(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_registration')

async def process_patent_migration_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_migration_card')

async def process_patent_dms(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_dms')

async def process_patent_patent(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_patent')

async def process_patent_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_inn')

async def process_patent_receipt(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_receipt')

async def process_patent_language_cert(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_language_cert')

async def process_patent_bank_details(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_bank_details')

async def process_patent_fingerprint_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent_fingerprint_card')

# Студент
async def process_student_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_snils')

async def process_student_registration(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_registration')

async def process_student_migration_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_migration_card')

async def process_student_dms(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_dms')

async def process_student_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_inn')

async def process_student_fingerprint_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_fingerprint_card')

async def process_student_university_cert(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_university_cert')

async def process_student_bank_details(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'student_bank_details')

# ЕАЭС
async def process_eaeas_registration(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_registration')

async def process_eaeas_migration_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_migration_card')

async def process_eaeas_dms(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_dms')

async def process_eaeas_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_inn')

async def process_eaeas_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_snils')

async def process_eaeas_fingerprint_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_fingerprint_card')

async def process_eaeas_bank_details(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'eaeas_bank_details')

# РВП
async def process_rvp_migration_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'rvp_migration_card')

async def process_rvp_dms_oms(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'rvp_dms_oms')

async def process_rvp_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'rvp_inn')

async def process_rvp_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'rvp_snils')

async def process_rvp_bank_details(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'rvp_bank_details')

# ВНЖ
async def process_vnzh_migration_card(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_migration_card')

async def process_vnzh_vnzh(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_vnzh')

async def process_vnzh_dms_oms(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_dms_oms')

async def process_vnzh_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_inn')

async def process_vnzh_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_snils')

async def process_vnzh_work_book(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_work_book')

async def process_vnzh_bank_details(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'vnzh_bank_details')


# Обработчики пропуска
async def skip_photo(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'photo')

async def skip_passport(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'passport')

# Патент
async def skip_patent_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_snils')

async def skip_patent_registration(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_registration')

async def skip_patent_migration_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_migration_card')

async def skip_patent_dms(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_dms')

async def skip_patent_patent(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_patent')

async def skip_patent_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_inn')

async def skip_patent_receipt(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_receipt')

async def skip_patent_language_cert(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_language_cert')

async def skip_patent_bank_details(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_bank_details')

async def skip_patent_fingerprint_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'patent_fingerprint_card')

# Студент
async def skip_student_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_snils')

async def skip_student_registration(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_registration')

async def skip_student_migration_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_migration_card')

async def skip_student_dms(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_dms')

async def skip_student_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_inn')

async def skip_student_fingerprint_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_fingerprint_card')

async def skip_student_university_cert(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_university_cert')

async def skip_student_bank_details(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'student_bank_details')

# ЕАЭС
async def skip_eaeas_registration(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_registration')

async def skip_eaeas_migration_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_migration_card')

async def skip_eaeas_dms(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_dms')

async def skip_eaeas_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_inn')

async def skip_eaeas_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_snils')

async def skip_eaeas_fingerprint_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_fingerprint_card')

async def skip_eaeas_bank_details(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'eaeas_bank_details')

# РВП
async def skip_rvp_migration_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'rvp_migration_card')

async def skip_rvp_dms_oms(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'rvp_dms_oms')

async def skip_rvp_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'rvp_inn')

async def skip_rvp_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'rvp_snils')

async def skip_rvp_bank_details(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'rvp_bank_details')

# ВНЖ
async def skip_vnzh_migration_card(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_migration_card')

async def skip_vnzh_vnzh(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_vnzh')

async def skip_vnzh_dms_oms(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_dms_oms')

async def skip_vnzh_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_inn')

async def skip_vnzh_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_snils')

async def skip_vnzh_work_book(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_work_book')

async def skip_vnzh_bank_details(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'vnzh_bank_details')

# Россия
async def process_russia_passport_propiska(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_passport_propiska')

async def process_russia_propiska(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_propiska')

async def process_russia_inn(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_inn')

async def process_russia_snils(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_snils')

async def process_russia_education_doc(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_education_doc')

async def process_russia_work_book(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_work_book')

async def process_russia_military_doc(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'russia_military_doc')

# Пропуск документов России
async def skip_russia_passport_propiska(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_passport_propiska')

async def skip_russia_propiska(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_propiska')

async def skip_russia_inn(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_inn')

async def skip_russia_snils(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_snils')

async def skip_russia_education_doc(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_education_doc')

async def skip_russia_work_book(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_work_book')

async def skip_russia_military_doc(message: types.Message, state: FSMContext):
    await _skip_document(message, state, 'russia_military_doc')


def register_document_handlers(dp, form_class):
    # Фото и паспорт (общие)
    dp.message.register(process_photo, form_class.photo, F.photo | F.document)
    dp.message.register(process_passport, form_class.passport, F.photo | F.document)

    # Документы Патента
    dp.message.register(process_patent_snils, form_class.patent_snils, F.photo | F.document)
    dp.message.register(process_patent_registration, form_class.patent_registration, F.photo | F.document)
    dp.message.register(process_patent_migration_card, form_class.patent_migration_card, F.photo | F.document)
    dp.message.register(process_patent_dms, form_class.patent_dms, F.photo | F.document)
    dp.message.register(process_patent_patent, form_class.patent_patent, F.photo | F.document)
    dp.message.register(process_patent_inn, form_class.patent_inn, F.photo | F.document)
    dp.message.register(process_patent_receipt, form_class.patent_receipt, F.photo | F.document)
    dp.message.register(process_patent_language_cert, form_class.patent_language_cert, F.photo | F.document)
    dp.message.register(process_patent_bank_details, form_class.patent_bank_details, F.photo | F.document)
    dp.message.register(process_patent_fingerprint_card, form_class.patent_fingerprint_card, F.photo | F.document)

    # Документы Студента
    dp.message.register(process_student_snils, form_class.student_snils, F.photo | F.document)
    dp.message.register(process_student_registration, form_class.student_registration, F.photo | F.document)
    dp.message.register(process_student_migration_card, form_class.student_migration_card, F.photo | F.document)
    dp.message.register(process_student_dms, form_class.student_dms, F.photo | F.document)
    dp.message.register(process_student_inn, form_class.student_inn, F.photo | F.document)
    dp.message.register(process_student_fingerprint_card, form_class.student_fingerprint_card, F.photo | F.document)
    dp.message.register(process_student_university_cert, form_class.student_university_cert, F.photo | F.document)
    dp.message.register(process_student_bank_details, form_class.student_bank_details, F.photo | F.document)

    # Документы ЕАЭС
    dp.message.register(process_eaeas_registration, form_class.eaeas_registration, F.photo | F.document)
    dp.message.register(process_eaeas_migration_card, form_class.eaeas_migration_card, F.photo | F.document)
    dp.message.register(process_eaeas_dms, form_class.eaeas_dms, F.photo | F.document)
    dp.message.register(process_eaeas_inn, form_class.eaeas_inn, F.photo | F.document)
    dp.message.register(process_eaeas_snils, form_class.eaeas_snils, F.photo | F.document)
    dp.message.register(process_eaeas_fingerprint_card, form_class.eaeas_fingerprint_card, F.photo | F.document)
    dp.message.register(process_eaeas_bank_details, form_class.eaeas_bank_details, F.photo | F.document)

    # Документы РВП
    dp.message.register(process_rvp_migration_card, form_class.rvp_migration_card, F.photo | F.document)
    dp.message.register(process_rvp_dms_oms, form_class.rvp_dms_oms, F.photo | F.document)
    dp.message.register(process_rvp_inn, form_class.rvp_inn, F.photo | F.document)
    dp.message.register(process_rvp_snils, form_class.rvp_snils, F.photo | F.document)
    dp.message.register(process_rvp_bank_details, form_class.rvp_bank_details, F.photo | F.document)

    # Документы ВНЖ
    dp.message.register(process_vnzh_migration_card, form_class.vnzh_migration_card, F.photo | F.document)
    dp.message.register(process_vnzh_vnzh, form_class.vnzh_vnzh, F.photo | F.document)
    dp.message.register(process_vnzh_dms_oms, form_class.vnzh_dms_oms, F.photo | F.document)
    dp.message.register(process_vnzh_inn, form_class.vnzh_inn, F.photo | F.document)
    dp.message.register(process_vnzh_snils, form_class.vnzh_snils, F.photo | F.document)
    dp.message.register(process_vnzh_work_book, form_class.vnzh_work_book, F.photo | F.document)
    dp.message.register(process_vnzh_bank_details, form_class.vnzh_bank_details, F.photo | F.document)

    # Документы Россия
    dp.message.register(process_russia_passport_propiska, form_class.russia_passport_propiska, F.photo | F.document)
    dp.message.register(process_russia_propiska, form_class.russia_propiska, F.photo | F.document)
    dp.message.register(process_russia_inn, form_class.russia_inn, F.photo | F.document)
    dp.message.register(process_russia_snils, form_class.russia_snils, F.photo | F.document)
    dp.message.register(process_russia_education_doc, form_class.russia_education_doc, F.photo | F.document)
    dp.message.register(process_russia_work_book, form_class.russia_work_book, F.photo | F.document)
    dp.message.register(process_russia_military_doc, form_class.russia_military_doc, F.photo | F.document)

    # Пропуск документов
    dp.message.register(skip_photo, form_class.photo, F.text == "⏭ Пропустить")
    dp.message.register(skip_passport, form_class.passport, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_snils, form_class.patent_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_registration, form_class.patent_registration, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_migration_card, form_class.patent_migration_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_dms, form_class.patent_dms, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_patent, form_class.patent_patent, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_inn, form_class.patent_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_receipt, form_class.patent_receipt, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_language_cert, form_class.patent_language_cert, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_bank_details, form_class.patent_bank_details, F.text == "⏭ Пропустить")
    dp.message.register(skip_patent_fingerprint_card, form_class.patent_fingerprint_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_snils, form_class.student_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_registration, form_class.student_registration, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_migration_card, form_class.student_migration_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_dms, form_class.student_dms, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_inn, form_class.student_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_fingerprint_card, form_class.student_fingerprint_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_university_cert, form_class.student_university_cert, F.text == "⏭ Пропустить")
    dp.message.register(skip_student_bank_details, form_class.student_bank_details, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_registration, form_class.eaeas_registration, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_migration_card, form_class.eaeas_migration_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_dms, form_class.eaeas_dms, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_inn, form_class.eaeas_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_snils, form_class.eaeas_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_fingerprint_card, form_class.eaeas_fingerprint_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_eaeas_bank_details, form_class.eaeas_bank_details, F.text == "⏭ Пропустить")
    dp.message.register(skip_rvp_migration_card, form_class.rvp_migration_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_rvp_dms_oms, form_class.rvp_dms_oms, F.text == "⏭ Пропустить")
    dp.message.register(skip_rvp_inn, form_class.rvp_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_rvp_snils, form_class.rvp_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_rvp_bank_details, form_class.rvp_bank_details, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_migration_card, form_class.vnzh_migration_card, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_vnzh, form_class.vnzh_vnzh, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_dms_oms, form_class.vnzh_dms_oms, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_inn, form_class.vnzh_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_snils, form_class.vnzh_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_work_book, form_class.vnzh_work_book, F.text == "⏭ Пропустить")
    dp.message.register(skip_vnzh_bank_details, form_class.vnzh_bank_details, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_passport_propiska, form_class.russia_passport_propiska, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_propiska, form_class.russia_propiska, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_inn, form_class.russia_inn, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_snils, form_class.russia_snils, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_education_doc, form_class.russia_education_doc, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_work_book, form_class.russia_work_book, F.text == "⏭ Пропустить")
    dp.message.register(skip_russia_military_doc, form_class.russia_military_doc, F.text == "⏭ Пропустить")

    # Ошибка: отправлен текст вместо файла
    all_states = [
        form_class.photo, form_class.passport,
        form_class.patent_snils, form_class.patent_registration,
        form_class.patent_migration_card, form_class.patent_dms,
        form_class.patent_patent, form_class.patent_inn,
        form_class.patent_receipt, form_class.patent_language_cert,
        form_class.patent_bank_details, form_class.patent_fingerprint_card,
        form_class.student_snils, form_class.student_registration,
        form_class.student_migration_card, form_class.student_dms,
        form_class.student_inn, form_class.student_fingerprint_card,
        form_class.student_university_cert, form_class.student_bank_details,
        form_class.eaeas_registration, form_class.eaeas_migration_card,
        form_class.eaeas_dms, form_class.eaeas_inn,
        form_class.eaeas_snils, form_class.eaeas_fingerprint_card,
        form_class.eaeas_bank_details,
        form_class.rvp_migration_card, form_class.rvp_dms_oms,
        form_class.rvp_inn, form_class.rvp_snils, form_class.rvp_bank_details,
        form_class.vnzh_migration_card, form_class.vnzh_vnzh,
        form_class.vnzh_dms_oms, form_class.vnzh_inn, form_class.vnzh_snils,
        form_class.vnzh_work_book, form_class.vnzh_bank_details,
        form_class.russia_passport_propiska, form_class.russia_propiska,
        form_class.russia_inn, form_class.russia_snils,
        form_class.russia_education_doc, form_class.russia_work_book,
        form_class.russia_military_doc,
    ]
    for state in all_states:
        dp.message.register(
            lambda message: message.answer("❌ Отправьте изображение или нажмите 'Пропустить'"),
            state, F.text
        )
