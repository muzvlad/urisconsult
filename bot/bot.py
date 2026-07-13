"""
Главный файл бота
"""
import asyncio
import glob
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, DOCS_DIR, ensure_dirs
from config.documents import DOC_LABELS
from handlers.commands import register_commands, get_start_keyboard
from handlers.registration import register_registration_handlers, WorkerForm
from handlers.documents import register_document_handlers
from handlers.confirmation import register_confirmation_handlers
from middleware import ThrottlingMiddleware
from services import db

# ─── Настройка логирования ──────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, "bot.log"),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8',
        ),
        logging.StreamHandler(),
    ]
)
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
    ensure_dirs()
    await db.init_db()
    await set_commands(bot)

    # Очистка старых temp-файлов
    temp_count = 0
    for f in glob.glob(os.path.join(DOCS_DIR, "temp_*")):
        try:
            os.remove(f)
            temp_count += 1
        except OSError:
            pass
    if temp_count:
        logger.info("Очищено %d временных файлов", temp_count)

    logger.info("Bot started successfully")


async def check_rejected_workers(bot: Bot):
    """Фоновая задача: проверка отклонённых анкет и отправка уведомлений."""
    while True:
        try:
            workers = await db.get_all_workers()
            for w in workers:
                if w.get('status') != 'rejected':
                    continue
                telegram_id = w.get('telegram_id')
                if not telegram_id:
                    continue

                reasons = w.get('rejection_reasons', '[]')
                if isinstance(reasons, str):
                    try:
                        reasons = json.loads(reasons)
                    except (json.JSONDecodeError, TypeError):
                        reasons = []

                if not reasons:
                    continue

                reasons_text = "\n".join(
                    f"  - {DOC_LABELS.get(r, r)}" for r in reasons
                )
                text = (
                    f"❌ Ваша анкета #{w['id']} отклонена.\n\n"
                    f"Необходимо исправить:\n{reasons_text}\n\n"
                    f"Отправьте исправленные данные через бота /start"
                )

                try:
                    await bot.send_message(chat_id=telegram_id, text=text)
                    logger.info("Отправлено уведомление об отклонении user=%s worker=%s",
                                telegram_id, w['id'])
                except Exception as e:
                    logger.warning("Не удалось отправить уведомление user=%s: %s",
                                   telegram_id, e)

        except Exception as e:
            logger.error("Ошибка проверки отклонённых анкет: %s", e)

        await asyncio.sleep(60)


async def main():
    """Главная функция запуска бота"""
    logger.info("Starting bot...")

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Rate limiting middleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=5, period=10.0))

    # Регистрация всех обработчиков
    register_commands(dp, WorkerForm)
    register_registration_handlers(dp, WorkerForm)
    register_document_handlers(dp, WorkerForm)
    register_confirmation_handlers(dp, WorkerForm)

    try:
        await on_startup(bot)
        # Запускаем фоновую задачу проверки отклонённых анкет
        asyncio.create_task(check_rejected_workers(bot))
        await dp.start_polling(bot)
    finally:
        await db.close_db()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
