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
from services.db_saver import DBSaver
from handlers.commands import cleanup_user_temp_files
from handlers.registration import WorkerForm

logger = logging.getLogger(__name__)

async def show_confirmation(message: types.Message, state: FSMContext):
    """Показать данные для подтверждения"""
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
    
    # Общие документы
    doc_checks = [
        ('📸 **Фото:**', 'photo_temp_path'),
        ('🪪 **Паспорт:**', 'passport_temp_path'),
    ]
    
    # Документы в зависимости от категории
    if citizenship == 'Патент':
        doc_checks.extend([
            ('📄 **СНИЛС:**', 'patent_snils_temp_path'),
            ('📋 **Регистрация:**', 'patent_registration_temp_path'),
            ('🎫 **Миграционная карта:**', 'patent_migration_card_temp_path'),
            ('🏥 **ДМС:**', 'patent_dms_temp_path'),
            ('📝 **Патент:**', 'patent_patent_temp_path'),
            ('🔢 **ИНН:**', 'patent_inn_temp_path'),
            ('🧾 **Чек по патенту:**', 'patent_receipt_temp_path'),
            ('🎓 **Сертификат языка:**', 'patent_language_cert_temp_path'),
            ('💳 **Реквизиты карты:**', 'patent_bank_details_temp_path'),
            ('🖐 **Дактилоскопия:**', 'patent_fingerprint_card_temp_path'),
        ])
    elif citizenship == 'Студент':
        doc_checks.extend([
            ('📄 **СНИЛС:**', 'student_snils_temp_path'),
            ('📋 **Регистрация:**', 'student_registration_temp_path'),
            ('🎫 **Миграционная карта:**', 'student_migration_card_temp_path'),
            ('🏥 **ДМС:**', 'student_dms_temp_path'),
            ('🔢 **ИНН:**', 'student_inn_temp_path'),
            ('🖐 **Дактилоскопия:**', 'student_fingerprint_card_temp_path'),
            ('🎓 **Справка из ВУЗа:**', 'student_university_cert_temp_path'),
            ('💳 **Реквизиты карты:**', 'student_bank_details_temp_path'),
        ])
    elif citizenship == 'ЕАЭС':
        doc_checks.extend([
            ('📋 **Регистрация:**', 'eaeas_registration_temp_path'),
            ('🎫 **Миграционная карта:**', 'eaeas_migration_card_temp_path'),
            ('🏥 **ДМС:**', 'eaeas_dms_temp_path'),
            ('🔢 **ИНН:**', 'eaeas_inn_temp_path'),
            ('📄 **СНИЛС:**', 'eaeas_snils_temp_path'),
            ('🖐 **Дактилоскопия:**', 'eaeas_fingerprint_card_temp_path'),
            ('💳 **Реквизиты карты:**', 'eaeas_bank_details_temp_path'),
        ])
    elif citizenship == 'РВП':
        doc_checks.extend([
            ('🎫 **Миграционная карта:**', 'rvp_migration_card_temp_path'),
            ('🏥 **ДМС/ОМС:**', 'rvp_dms_oms_temp_path'),
            ('🔢 **ИНН:**', 'rvp_inn_temp_path'),
            ('📄 **СНИЛС:**', 'rvp_snils_temp_path'),
            ('💳 **Реквизиты карты:**', 'rvp_bank_details_temp_path'),
        ])
    elif citizenship == 'ВНЖ':
        doc_checks.extend([
            ('🎫 **Миграционная карта:**', 'vnzh_migration_card_temp_path'),
            ('🪪 **ВНЖ:**', 'vnzh_vnzh_temp_path'),
            ('🏥 **ДМС/ОМС:**', 'vnzh_dms_oms_temp_path'),
            ('🔢 **ИНН:**', 'vnzh_inn_temp_path'),
            ('📄 **СНИЛС:**', 'vnzh_snils_temp_path'),
            ('📖 **Трудовая книжка/ЭТК:**', 'vnzh_work_book_temp_path'),
            ('💳 **Реквизиты карты:**', 'vnzh_bank_details_temp_path'),
        ])
    elif citizenship == 'Россия':
        doc_checks.extend([
            ('📖 **Паспорт прописка:**', 'russia_passport_propiska_temp_path'),
            ('📋 **Прописка:**', 'russia_propiska_temp_path'),
            ('🔢 **ИНН:**', 'russia_inn_temp_path'),
            ('📄 **СНИЛС:**', 'russia_snils_temp_path'),
            ('🎓 **Документ об образовании:**', 'russia_education_doc_temp_path'),
            ('📖 **Трудовая книжка/ЭТК:**', 'russia_work_book_temp_path'),
            ('🎖 **Военный билет/Приписное:**', 'russia_military_doc_temp_path'),
        ])
    
    # Дополнительные поля для России (мужчины)
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
    
    for label, key in doc_checks:
        status = '✅' if data.get(key) else '❌'
        text += f"{label} {status}\n"
    
    text += "\nВсе верно?"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_confirmation_keyboard())
    await state.set_state(WorkerForm.confirmation)

async def process_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка подтверждения"""
    if callback.data == "confirm":
        await callback.message.edit_text("⏳ Сохраняем данные...")
        
        # Получаем все данные
        data = await state.get_data()
        user = callback.from_user
        citizenship = data.get('citizenship', '')
        
        # Сохраняем документы
        saved_files = {}
        doc_types = [
            'photo', 'passport',
            'patent_snils', 'patent_registration', 'patent_migration_card',
            'patent_dms', 'patent_patent', 'patent_inn', 'patent_receipt',
            'patent_language_cert', 'patent_bank_details', 'patent_fingerprint_card',
            'student_snils', 'student_registration', 'student_migration_card',
            'student_dms', 'student_inn', 'student_fingerprint_card',
            'student_university_cert', 'student_bank_details',
            'eaeas_registration', 'eaeas_migration_card', 'eaeas_dms',
            'eaeas_inn', 'eaeas_snils', 'eaeas_fingerprint_card', 'eaeas_bank_details',
            'rvp_migration_card', 'rvp_dms_oms', 'rvp_inn', 'rvp_snils', 'rvp_bank_details',
            'vnzh_migration_card', 'vnzh_vnzh', 'vnzh_dms_oms', 'vnzh_inn', 'vnzh_snils',
            'vnzh_work_book', 'vnzh_bank_details',
            'russia_passport_propiska', 'russia_propiska', 'russia_inn', 'russia_snils',
            'russia_education_doc', 'russia_work_book', 'russia_military_doc'
        ]
        
        worker_id = await DBSaver.get_next_id()
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
        
        # Сохраняем в БД
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