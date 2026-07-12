"""
Обработчики подтверждения и редактирования.

Работает с нормализованной БД и общим конфигом документов.
"""
import os
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config.documents import DOC_FLOWS, get_doc_by_key, DOC_LABELS
from keyboards.reply_kb import get_confirmation_keyboard, get_edit_keyboard
from services.file_saver import FileSaver
from services.db_saver import DBSaver
from handlers.commands import cleanup_user_temp_files
from handlers.registration import WorkerForm

logger = logging.getLogger(__name__)


async def show_confirmation(message: types.Message, state: FSMContext):
    """Показать данные для подтверждения."""
    data = await state.get_data()
    citizenship = data.get('citizenship', '')

    # Формируем сообщение с данными
    text = "📋 **Проверьте введенные данные:**\n\n"
    text += f"📝 **ФИО:** {data.get('name', 'Не указано')}\n"
    text += f"🌍 **Категория:** {citizenship}\n"
    text += f"⚥ **Пол:** {data.get('gender', 'Не указано')}\n"
    text += f"💼 **Должность:** {data.get('position', 'Не указано')}\n"
    text += f"🏢 **Объект:** {data.get('object', 'Не указано')}\n"
    text += f"📍 **Адрес:** {data.get('object_address', 'Не указано')}\n"
    text += f"👤 **Менеджер:** {data.get('manager', 'Не указано')}\n"
    text += f"📞 **Основной тел.:** {data.get('phone_main', 'Не указано')}\n"
    text += f"📞 **Доп. тел.:** {data.get('phone_additional', 'Не указано')}\n"
    text += f"📧 **Email:** {data.get('email', 'Не указано')}\n"
    text += f"📅 **Дата рождения:** {data.get('date', 'Не указано')}\n\n"

    # Документы
    text += "📎 **Загруженные файлы:**\n"

    if citizenship in DOC_FLOWS:
        for doc in DOC_FLOWS[citizenship]:
            temp_key = f'{doc.key}_temp_path'
            has_file = bool(data.get(temp_key))
            status = '✅' if has_file else '❌'
            text += f"{doc.label}: {status}\n"

    # Дополнительные поля для России
    if citizenship == 'Россия':
        text += "\n👤 **Дополнительная информация:**\n"
        text += f"👨 **Пол:** {data.get('gender', 'Не указано')}\n"
        text += f"💍 **Семейное положение:** {data.get('russia_marital_status', 'Не указано')}\n"

        relatives = data.get('russia_relatives_list', [])
        if relatives:
            text += "👨‍👩‍👧‍👦 **Родственники:**\n"
            for i, rel in enumerate(relatives, 1):
                text += f"  {i}. {rel.get('name', '')}, {rel.get('birth_year', '')}, {rel.get('phone', '')}\n"
        else:
            text += "👨‍👩‍👧‍👦 **Родственники:** Не указаны\n"

    text += "\nВсе верно?"

    await message.answer(text, parse_mode="Markdown", reply_markup=get_confirmation_keyboard())
    await state.set_state(WorkerForm.confirmation)


async def process_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка подтверждения."""
    if callback.data == "confirm":
        await callback.message.edit_text("⏳ Сохраняем данные...")

        data = await state.get_data()
        user = callback.from_user
        citizenship = data.get('citizenship', '')

        # Сохраняем документы
        saved_files = {}
        if citizenship in DOC_FLOWS:
            for doc in DOC_FLOWS[citizenship]:
                temp_path = data.get(f'{doc.key}_temp_path')
                if temp_path and os.path.exists(temp_path):
                    try:
                        saved_filename = FileSaver.save_document(
                            temp_path, data.get('id', ''), doc.key
                        )
                        saved_files[doc.key] = saved_filename
                    except Exception as e:
                        logger.error("Ошибка сохранения %s: %s", doc.key, e)

        data['saved_files'] = saved_files

        try:
            worker_id, _ = await DBSaver.save_worker_data(
                user_id=user.id,
                data=data,
                telegram_username=user.username
            )

            logger.info("Сохранен работник: %s (ID: %s)", data.get('name', ''), worker_id)

            await callback.message.edit_text(
                f"✅ **Данные успешно сохранены!**\n\n"
                f"🆔 **ID работника:** {worker_id}\n"
                f"📝 **ФИО:** {data.get('name', 'Не указано')}\n\n"
                f"Благодарим за заполнение анкеты!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Ошибка сохранения в БД: %s", e, exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при сохранении данных. Попробуйте позже."
            )

        await state.clear()

        temp_files = data.get('temp_files', [])
        FileSaver.cleanup_temp_files(temp_files)

    elif callback.data == "restart":
        await state.clear()
        cleanup_user_temp_files(callback.from_user.id)
        await callback.message.edit_text(
            "🔄 Начинаем заполнение заново.\n"
            "Введите ваше ФИО:"
        )
        await state.set_state(WorkerForm.name)

    elif callback.data == "edit":
        await callback.message.edit_text(
            "✏️ Выберите поле, которое хотите исправить:",
            reply_markup=get_edit_keyboard()
        )
        await state.set_state(WorkerForm.edit)


async def process_edit(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования."""
    if callback.data == "edit_done":
        await show_confirmation(callback.message, state)
        await callback.answer()
        return

    field = callback.data.replace("edit_", "")
    await state.update_data(editing_field=field)

    field_names = {
        'name': '📝 ФИО',
        'citizenship': '🌍 Гражданство',
        'gender': '⚥ Пол',
        'position': '💼 Должность',
        'object': '🏢 Объект',
        'object_address': '📍 Адрес объекта',
        'manager': '👤 Менеджер',
        'phone_main': '📞 Основной телефон',
        'phone_additional': '📞 Дополнительный телефон',
        'email': '📧 Email',
        'date': '📅 Дата рождения',
        'photo': '📸 Фото',
        'passport': '🪪 Паспорт',
        'registration': '📋 Регистрация',
    }

    field_name = field_names.get(field, field)
    await callback.message.edit_text(
        f"✏️ Введите новое значение для поля {field_name}:"
    )
    await state.set_state(WorkerForm.edit)


async def process_edit_value(message: types.Message, state: FSMContext):
    """Обработка нового значения для редактируемого поля."""
    data = await state.get_data()
    field = data.get('editing_field')

    if not field:
        await message.answer("❌ Ошибка. Начните редактирование заново.")
        await state.clear()
        return

    await state.update_data(**{field: message.text.strip()})
    await show_confirmation(message, state)


def register_confirmation_handlers(dp, form_class):
    """Регистрация обработчиков подтверждения."""
    dp.callback_query.register(process_confirmation, form_class.confirmation)
    dp.callback_query.register(process_edit, form_class.edit, F.data.startswith("edit_"))
    dp.message.register(process_edit_value, form_class.edit)
