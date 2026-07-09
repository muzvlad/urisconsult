"""
Главный файл бота
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN
from handlers.commands import register_commands, get_start_keyboard
from handlers.registration import register_registration_handlers, WorkerForm
from handlers.documents import register_document_handlers
from handlers.confirmation import register_confirmation_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Убираем шум от библиотек
logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

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
    await set_commands(bot)
    logger.info("Бот запущен и готов к работе")

async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота...")
    
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
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())