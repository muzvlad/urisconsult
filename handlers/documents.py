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
from keyboards.reply_kb import get_skip_keyboard
from handlers.registration import WorkerForm
from handlers.confirmation import show_confirmation

logger = logging.getLogger(__name__)

DOC_PROMPTS = {
    'photo': ("📸 Фото получено. Теперь отправьте скан паспорта:", WorkerForm.passport),
    'passport': ("✅ Скан паспорта получен. Теперь отправьте скан патента:", WorkerForm.patent),
    'patent': ("✅ Скан патента получен. Теперь отправьте скан регистрации:", WorkerForm.registration),
}

def _validate_extension(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ALLOWED_EXTENSIONS

async def _download_document(message: types.Message, state: FSMContext, bot: Bot, doc_type: str) -> bool:
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
        temp_path = os.path.join(DOCS_DIR, f"temp_{doc_type}_{message.from_user.id}{ext}")

        await bot.download_file(file_path, temp_path)

        data = await state.get_data()
        temp_files = data.get('temp_files', [])
        temp_files.append(temp_path)
        await state.update_data(**{f'{doc_type}_temp_path': temp_path, 'temp_files': temp_files})

        if doc_type in DOC_PROMPTS:
            prompt_text, next_state = DOC_PROMPTS[doc_type]
            await message.answer(prompt_text, reply_markup=get_skip_keyboard())
            await state.set_state(next_state)
        else:
            await message.answer("✅ Все документы получены!", reply_markup=ReplyKeyboardRemove())
            await show_confirmation(message, state)

        return True
    except Exception as e:
        logger.error("Ошибка при загрузке %s: %s", doc_type, e)
        await message.answer("❌ Ошибка при загрузке. Попробуйте еще раз или нажмите 'Пропустить':")
        return False

async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'photo')

async def process_passport(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'passport')

async def process_patent(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'patent')

async def process_registration(message: types.Message, state: FSMContext, bot: Bot):
    await _download_document(message, state, bot, 'registration')

def register_document_handlers(dp, form_class):
    dp.message.register(process_photo, form_class.photo, F.photo | F.document)
    dp.message.register(process_passport, form_class.passport, F.photo | F.document)
    dp.message.register(process_patent, form_class.patent, F.photo | F.document)
    dp.message.register(process_registration, form_class.registration, F.photo | F.document)

    dp.message.register(
        lambda message: message.answer("❌ Отправьте изображение или нажмите 'Пропустить'"),
        form_class.photo, F.text
    )
    dp.message.register(
        lambda message: message.answer("❌ Отправьте изображение или нажмите 'Пропустить'"),
        form_class.passport, F.text
    )
    dp.message.register(
        lambda message: message.answer("❌ Отправьте изображение или нажмите 'Пропустить'"),
        form_class.patent, F.text
    )
    dp.message.register(
        lambda message: message.answer("❌ Отправьте изображение или нажмите 'Пропустить'"),
        form_class.registration, F.text
    )
