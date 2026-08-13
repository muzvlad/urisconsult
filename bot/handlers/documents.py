"""
Обработчики документов — generic approach.

Вместо 60+ функций-обработчиков — одна process_document + динамическая регистрация.
"""
import os
import logging
from aiogram import types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config import DOCS_DIR
from config.documents import (
    DOC_FLOWS, DOC_PROMPTS, get_doc_flow, get_next_doc, get_doc_by_key,
)
from services.file_saver import FileSaver
from keyboards.reply_kb import get_skip_keyboard
from handlers.confirmation import show_confirmation
from utils import get_document_state, validate_file_extension

logger = logging.getLogger(__name__)


# ─── Скачивание документа ───────────────────────────────────────────

async def _download_document(message: types.Message, state: FSMContext, bot: Bot,
                             doc_key: str) -> bool:
    """Скачать документ и перейти к следующему в цепочке."""
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
        else:
            file_id = message.document.file_id

        file = await bot.get_file(file_id)
        file_path = file.file_path

        if not validate_file_extension(file_path):
            await message.answer(
                f"❌ Недопустимый формат файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}\n"
                "Попробуйте еще раз или нажмите 'Пропустить':"
            )
            return False

        ext = os.path.splitext(file_path)[1] or '.jpg'
        data = await state.get_data()
        doc = get_doc_by_key(doc_key)
        is_multi = bool(doc and doc.multi_file)

        temp_files = data.get('temp_files', [])

        if is_multi:
            # multi_file документ: уникальный temp-путь на каждый файл
            paths = data.get(f'{doc_key}_temp_paths', [])
            temp_path = os.path.join(
                DOCS_DIR, f"temp_{doc_key}_{len(paths) + 1}_{message.from_user.id}{ext}"
            )
        else:
            temp_path = os.path.join(DOCS_DIR, f"temp_{doc_key}_{message.from_user.id}{ext}")

        await bot.download_file(file_path, temp_path)

        if is_multi:
            paths.append(temp_path)
            temp_files.append(temp_path)
            await state.update_data(**{f'{doc_key}_temp_paths': paths, 'temp_files': temp_files})
            await message.answer(
                "✅ Файл получен!\n"
                "Пришлите ещё файл или нажмите 'Пропустить', чтобы завершить:",
                reply_markup=get_skip_keyboard()
            )
            return True

        temp_files.append(temp_path)
        await state.update_data(**{f'{doc_key}_temp_path': temp_path, 'temp_files': temp_files})

        # Если estamos в режиме исправления — переходим к следующему отклонённому полю
        fix_reasons = data.get('fix_reasons', [])
        fix_index = data.get('fix_index', -1)
        if fix_reasons and fix_index >= 0:
            from handlers.commands import _ask_rejected_field
            next_index = fix_index + 1
            if next_index < len(fix_reasons):
                next_reason = fix_reasons[next_index]
                next_field = next_reason['key'] if isinstance(next_reason, dict) else str(next_reason)
                await _ask_rejected_field(message, state, next_field,
                                          fix_reasons, next_index)
            else:
                from handlers.confirmation import show_confirmation
                await message.answer("✅ Все замечания исправлены!",
                                     reply_markup=ReplyKeyboardRemove())
                await show_confirmation(message, state)
            return True

        # Обычный режим — переходим к следующему документу
        citizenship = data.get('citizenship', 'Патент')
        await _go_next(message, state, doc_key, citizenship)

        return True
    except Exception as e:
        logger.error("Ошибка при загрузке %s: %s", doc_key, e)
        await message.answer("❌ Ошибка при загрузке. Попробуйте еще раз или нажмите 'Пропустить':")
        return False


# ─── Пропуск документа ──────────────────────────────────────────────

async def _skip_document(message: types.Message, state: FSMContext, doc_key: str):
    """Пропустить документ и перейти к следующему."""
    data = await state.get_data()

    doc = get_doc_by_key(doc_key)
    is_multi = bool(doc and doc.multi_file)
    multi_paths = data.get(f'{doc_key}_temp_paths', []) if is_multi else []

    # multi_file с загруженными файлами — «Пропустить» = завершить сбор
    if not (is_multi and multi_paths):
        await state.update_data(**{f'{doc_key}_temp_path': None})

    # Если estamos в режиме исправления — переходим к следующему отклонённому полю
    fix_reasons = data.get('fix_reasons', [])
    fix_index = data.get('fix_index', -1)
    if fix_reasons and fix_index >= 0:
        from handlers.commands import _ask_rejected_field
        next_index = fix_index + 1
        if next_index < len(fix_reasons):
            next_reason = fix_reasons[next_index]
            next_field = next_reason['key'] if isinstance(next_reason, dict) else str(next_reason)
            await _ask_rejected_field(message, state, next_field,
                                      fix_reasons, next_index)
        else:
            from handlers.confirmation import show_confirmation
            await message.answer("✅ Все замечания исправлены!",
                                 reply_markup=ReplyKeyboardRemove())
            await show_confirmation(message, state)
        return

    # Обычный режим
    citizenship = data.get('citizenship', 'Патент')
    await _go_next(message, state, doc_key, citizenship)


# ─── Переход к следующему документу ─────────────────────────────────

async def _go_next(message: types.Message, state: FSMContext,
                   current_doc_key: str, citizenship: str):
    """Перейти к следующему документу или завершить сбор."""
    from handlers.registration import get_worker_form
    WorkerForm = get_worker_form()

    next_item = get_next_doc(current_doc_key, citizenship)
    if next_item:
        skip_text = "\nИли нажмите 'Пропустить'" if next_item.can_skip else ""
        await message.answer(
            DOC_PROMPTS.get(next_item.key, f"Отправьте {next_item.label}:") + skip_text,
            reply_markup=get_skip_keyboard()
        )
        await state.set_state(getattr(WorkerForm, next_item.key))
    else:
        await message.answer("✅ Все документы получены!", reply_markup=ReplyKeyboardRemove())
        await _after_documents(message, state)


# ─── После сбора документов ─────────────────────────────────────────

async def _after_documents(message: types.Message, state: FSMContext):
    """Обработка после сбора документов.

    Для России: дополнительные поля (семейное положение, родственники).
    Семейное положение запрашивается ТОЛЬКО для мужчин — это осознанное решение,
    т.к. семейное положение влияет на воинский учёт и льготы."""
    from handlers.registration import get_worker_form
    WorkerForm = get_worker_form()
    from keyboards.reply_kb import get_marital_keyboard

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


# ─── Универсальный обработчик ──────────────────────────────────────

async def process_document(message: types.Message, state: FSMContext, bot: Bot,
                           doc_key: str):
    """Единый обработчик для ВСЕХ типов документов."""
    await _download_document(message, state, bot, doc_key)


async def skip_document(message: types.Message, state: FSMContext, doc_key: str):
    """Единый обработчик пропуска для ВСЕХ типов документов."""
    await _skip_document(message, state, doc_key)


# ─── Динамическая регистрация обработчиков ─────────────────────────

def register_document_handlers(dp, form_class):
    """Регистрация обработчиков для ВСЕХ документов из конфига."""
    from utils import get_all_doc_keys

    for doc_key in get_all_doc_keys():
        state = getattr(form_class, doc_key)

        def make_doc_handler(dk):
            async def handler(message: types.Message, state: FSMContext, bot: Bot):
                await process_document(message, state, bot, dk)
            return handler

        def make_skip_handler(dk):
            async def handler(message: types.Message, state: FSMContext):
                await skip_document(message, state, dk)
            return handler

        async def reject_text(message: types.Message):
            await message.answer("❌ Отправьте изображение или нажмите 'Пропустить'")

        dp.message.register(make_doc_handler(doc_key), state, F.photo | F.document)
        dp.message.register(make_skip_handler(doc_key), state, F.text == "⏭ Пропустить")
        dp.message.register(reject_text, state, F.text)
