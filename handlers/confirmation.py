"""
Обработчики подтверждения и редактирования
"""
import os
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from keyboards.reply_kb import get_confirmation_keyboard, get_edit_keyboard
from services.file_saver import FileSaver
from services.json_saver import JSONSaver
from handlers.commands import cleanup_user_temp_files
from handlers.registration import WorkerForm

logger = logging.getLogger(__name__)

async def show_confirmation(message: types.Message, state: FSMContext):
    """Показать данные для подтверждения"""
    data = await state.get_data()
    
    # Формируем сообщение с данными
    text = "📋 **Проверьте введенные данные:**\n\n"
    text += f"📝 **ФИО:** {data.get('name', 'Не указано')}\n"
    text += f"🌍 **Гражданство:** {data.get('citizenship', 'Не указано')}\n"
    text += f"⚥ **Пол:** {data.get('gender', 'Не указано')}\n"
    text += f"💼 **Должность:** {data.get('position', 'Не указано')}\n"
    text += f"🏢 **Объект:** {data.get('object', 'Не указано')}\n"
    text += f"📍 **Адрес:** {data.get('object_address', 'Не указано')}\n"
    text += f"👤 **Менеджер:** {data.get('manager', 'Не указано')}\n"
    text += f"📞 **Основной тел.:** {data.get('phone_main', 'Не указано')}\n"
    text += f"📞 **Доп. тел.:** {data.get('phone_additional', 'Не указано')}\n"
    text += f"📧 **Email:** {data.get('email', 'Не указано')}\n"
    text += f"📅 **Дата рождения:** {data.get('date', 'Не указано')}\n\n"
    
    text += "📎 **Загруженные файлы:**\n"
    text += f"📸 **Фото:** {'✅' if data.get('photo_temp_path') else '❌'}\n"
    text += f"🪪 **Паспорт:** {'✅' if data.get('passport_temp_path') else '❌'}\n"
    text += f"📄 **Патент:** {'✅' if data.get('patent_temp_path') else '❌'}\n"
    text += f"📋 **Регистрация:** {'✅' if data.get('registration_temp_path') else '❌'}\n\n"
    
    text += "Все верно?"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_confirmation_keyboard())
    await state.set_state(WorkerForm.confirmation)

async def process_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка подтверждения"""
    if callback.data == "confirm":
        await callback.message.edit_text("⏳ Сохраняем данные...")
        
        # Получаем все данные
        data = await state.get_data()
        user = callback.from_user
        
        # Сохраняем документы
        saved_files = {}
        doc_types = ['photo', 'passport', 'patent', 'registration']
        
        worker_id = JSONSaver.get_next_id()
        data['id'] = worker_id
        
        for doc_type in doc_types:
            temp_path = data.get(f'{doc_type}_temp_path')
            if temp_path and os.path.exists(temp_path):
                try:
                    saved_filename = FileSaver.save_document(temp_path, worker_id, doc_type)
                    saved_files[doc_type] = saved_filename
                except Exception as e:
                    logger.error(f"Ошибка сохранения {doc_type}: {e}")
        
        # Добавляем сохраненные файлы в данные
        data['saved_files'] = saved_files
        
        # Сохраняем JSON
        try:
            worker_id, filename = JSONSaver.save_worker_data(
                user_id=user.id,
                data=data,
                telegram_username=user.username
            )
            
            logger.info("JSON сохранен: %s (ID: %s)", filename, worker_id)
            
            await callback.message.edit_text(
                f"✅ **Данные успешно сохранены!**\n\n"
                f"🆔 **ID работника:** {worker_id}\n"
                f"📝 **ФИО:** {data.get('name', 'Не указано')}\n\n"
                f"Благодарим за заполнение анкеты!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Ошибка сохранения JSON: %s", e, exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при сохранении данных. Попробуйте позже."
            )
        
        # Очищаем состояние
        await state.clear()
        
        # Очищаем временные файлы
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
    """Обработка выбора поля для редактирования"""
    if callback.data == "edit_done":
        # Возвращаемся к подтверждению
        await show_confirmation(callback.message, state)
        await callback.answer()
        return
    
    # Извлекаем название поля из callback_data
    field = callback.data.replace("edit_", "")
    
    # Сохраняем поле, которое будем редактировать
    await state.update_data(editing_field=field)
    
    # Отправляем запрос на ввод нового значения
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
        'patent': '📄 Патент',
        'registration': '📋 Регистрация'
    }
    
    field_name = field_names.get(field, field)
    
    await callback.message.edit_text(
        f"✏️ Введите новое значение для поля {field_name}:"
    )
    
    # Устанавливаем состояние для редактирования
    await state.set_state(WorkerForm.edit)

async def process_edit_value(message: types.Message, state: FSMContext):
    """Обработка нового значения для редактируемого поля"""
    data = await state.get_data()
    field = data.get('editing_field')
    
    if not field:
        await message.answer("❌ Ошибка. Начните редактирование заново.")
        await state.clear()
        return
    
    # Обновляем значение
    await state.update_data({field: message.text.strip()})
    
    # Возвращаемся к подтверждению
    await show_confirmation(message, state)

def register_confirmation_handlers(dp, form_class):
    """Регистрация обработчиков подтверждения"""
    dp.callback_query.register(process_confirmation, form_class.confirmation)
    dp.callback_query.register(process_edit, form_class.edit, F.data.startswith("edit_"))
    dp.message.register(process_edit_value, form_class.edit)