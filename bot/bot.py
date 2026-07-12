"""
Главный файл бота
"""
import asyncio
import glob
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, DOCS_DIR
from handlers.commands import register_commands, get_start_keyboard
from handlers.registration import register_registration_handlers, WorkerForm
from handlers.documents import register_document_handlers
from handlers.confirmation import register_confirmation_handlers
from services import db

# Настройка логирования — только ошибки
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger('aiogram').setLevel(logging.ERROR)
logging.getLogger('aiohttp').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="Начать регистрацию"),
        BotCommand(command="cancel", description="Отменить заполнение")
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    await db.init_db()
    await set_commands(bot)
    for f in glob.glob(os.path.join(DOCS_DIR, "temp_*")):
        os.remove(f)
    print("Bot started")

async def main():
    """Главная функция запуска бота"""
    print("Starting bot...")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация всех обработчиков
    register_commands(dp, WorkerForm)
    register_registration_handlers(dp, WorkerForm)
    register_document_handlers(dp, WorkerForm)
    register_confirmation_handlers(dp, WorkerForm)
    
    # Запуск поллинга
    try:
        await on_startup(bot)
        await dp.start_polling(bot)
    finally:
        await db.close_db()
        await bot.session.close()
        print("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())