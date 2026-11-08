"""
Главный файл бота
"""
import asyncio
import glob
import json
import os
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher
from services.fsm_storage import SQLiteStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, DOCS_DIR, DB_PATH, API_PORT, API_TOKEN, ensure_dirs
from config.documents import FIELD_LABELS
from handlers.commands import register_commands, get_start_keyboard
from handlers.registration import register_registration_handlers, get_worker_form
from handlers.documents import register_document_handlers
from handlers.confirmation import register_confirmation_handlers
from middleware import ThrottlingMiddleware
from services import db
from shared import now_msk
from log_context import setup_logging_filters

# ─── Настройка логирования ──────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s [uid=%(user_id)s w=%(worker_id)s]: %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, "bot.log"),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8',
        ),
    ]
)
# В консоль — INFO и выше, с автоочисткой
class AutoClearConsoleHandler(logging.StreamHandler):
    """Handler который очищает консоль каждые N сообщений."""
    def __init__(self, stream=None, clear_after=100):
        super().__init__(stream)
        self.clear_after = clear_after
        self.msg_count = 0

    def emit(self, record):
        self.msg_count += 1
        if self.msg_count >= self.clear_after:
            self.msg_count = 0
            clear_console()
            console_print("=" * 50, 'green')
            console_print("  URIS CONSULT BOT — РАБОТАЕТ", 'green')
            console_print("=" * 50, 'green')
            console_print(f"  БД: {DB_PATH}")
            console_print(f"  Документы: {DOCS_DIR}")
            console_print("=" * 50, 'green')
        super().emit(record)

_console = AutoClearConsoleHandler(clear_after=20)
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger().addHandler(_console)

logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ─── Консольный вывод ──────────────────────────────────────────────

def clear_console():
    """Очистка терминала."""
    os.system('cls' if os.name == 'nt' else 'clear')

def console_print(msg, color='white'):
    """Цветной вывод в консоль."""
    colors = {'green': '\033[92m', 'red': '\033[91m', 'yellow': '\033[93m', 'white': ''}
    reset = '\033[0m'
    c = colors.get(color, '')
    print(f"{c}{msg}{reset}", flush=True)


def _start_api_server():
    """Запустить Flask API-сервер в фоновом потоке."""
    try:
        from api_server import app

        def _run():
            try:
                app.run(host='0.0.0.0', port=API_PORT, debug=False, use_reloader=False,
                        threaded=True)
            except Exception as e:
                console_print(f"  ОШИБКА API-потока: {e}", 'red')
                logger.error("API server thread crashed: %s", e)

        t = threading.Thread(target=_run, daemon=True, name="api-server")
        t.start()
        import time
        time.sleep(1)
        if t.is_alive():
            console_print(f"  API-сервер: http://0.0.0.0:{API_PORT}", 'green')
        else:
            console_print(f"  ОШИБКА API-сервера: поток умер", 'red')
    except Exception as e:
        console_print(f"  ОШИБКА API-сервера: {e}", 'red')
        logger.error("Failed to start API server: %s", e)


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
    setup_logging_filters()
    await db.init_db()
    await set_commands(bot)

    # Запуск API-сервера в фоновом потоке
    _start_api_server()

    # Очистка старых temp-файлов
    temp_count = 0
    for f in glob.glob(os.path.join(DOCS_DIR, "temp_*")):
        try:
            os.remove(f)
            temp_count += 1
        except OSError:
            pass

    clear_console()
    console_print("=" * 50, 'green')
    console_print("  URIS CONSULT BOT — РАБОТАЕТ", 'green')
    console_print("=" * 50, 'green')
    console_print(f"  БД: {DB_PATH}")
    console_print(f"  Документы: {DOCS_DIR}")
    console_print(f"  API: http://0.0.0.0:{API_PORT}")
    if not API_TOKEN:
        console_print("  [ВНИМАНИЕ] API без авторизации — задайте API_TOKEN в bot/.env", 'yellow')
    if temp_count:
        console_print(f"  Очищено {temp_count} temp-файлов")
    console_print("=" * 50, 'green')


async def check_rejected_workers(bot: Bot):
    """Фоновая задача: проверка отклонённых анкет и отправка уведомлений с inline кнопками."""
    while True:
        try:
            workers = await db.get_unnotified_rejected_workers()
            for w in workers:
                telegram_id = w.get('telegram_id')
                if not telegram_id:
                    continue

                worker_id = w['id']

                from utils import parse_rejection_reasons

                parsed = parse_rejection_reasons(w.get('rejection_reasons', '[]'))

                if not parsed:
                    continue

                def _fmt(r):
                    key = r.get('key', '') if isinstance(r, dict) else str(r)
                    comment = r.get('comment', '') if isinstance(r, dict) else ''
                    line = f"  - {FIELD_LABELS.get(key, key)}"
                    if comment:
                        line += f"\n    📝 {comment}"
                    return line

                reasons_text = "\n".join(_fmt(r) for r in parsed)
                text = (
                    f"❌ Ваша анкета #{worker_id} отклонена.\n\n"
                    f"Необходимо исправить:\n{reasons_text}"
                )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Исправить анкету",
                                             callback_data=f"fix_rejected:{worker_id}"),
                        InlineKeyboardButton(text="Новая анкета",
                                             callback_data=f"new_rejected:{worker_id}"),
                    ]
                ])

                try:
                    await bot.send_message(chat_id=telegram_id, text=text,
                                           reply_markup=keyboard)
                    await db.mark_notified(worker_id)
                    logger.info("Уведомление отправлено user=%s worker=%s",
                                telegram_id, worker_id)
                except Exception as e:
                    logger.warning("Не удалось отправить user=%s: %s",
                                   telegram_id, e)

        except Exception as e:
            logger.error("Ошибка проверки отклонённых: %s", e)

        await asyncio.sleep(60)


async def check_meeting_notifications(bot: Bot):
    """Фоновая задача: уведомления о встречах и напоминания за 24 часа."""
    from datetime import timedelta
    from utils import parse_meeting_datetime

    while True:
        now = now_msk()
        try:
            for m in await db.get_unnotified_meetings():
                meeting_at = parse_meeting_datetime(m.get('date', ''))
                meeting_id = m['id']
                if not m.get('telegram_id'):
                    await db.mark_meeting_notified(meeting_id, 'no_telegram')
                    await db.mark_meeting_reminded(meeting_id, 'no_telegram')
                    continue
                if meeting_at is None:
                    logger.warning("Некорректная дата встречи id=%s: %s",
                                   meeting_id, m.get('date'))
                    await db.mark_meeting_notified(meeting_id, 'invalid_date')
                    await db.mark_meeting_reminded(meeting_id, 'invalid_date')
                    continue

                text = (
                    f"Вам назначена встреча\n"
                    f"ФИО: {m.get('worker_name', '')}\n"
                    f"Дата и время: {m.get('date', '')}\n"
                )
                if m.get('note'):
                    text += f"Примечание: {m['note']}\n"
                try:
                    await bot.send_message(chat_id=m['telegram_id'], text=text)
                    await db.mark_meeting_notified(meeting_id, now.isoformat())
                except Exception as e:
                    logger.warning("Не удалось отправить встречу id=%s: %s", meeting_id, e)
                    continue

                # Встреча уже в пределах 24 часов — напоминание не дублируем
                if meeting_at - now <= timedelta(hours=24):
                    await db.mark_meeting_reminded(meeting_id, now.isoformat())

            for m in await db.get_meetings_to_remind():
                meeting_at = parse_meeting_datetime(m.get('date', ''))
                meeting_id = m['id']
                if not m.get('telegram_id'):
                    await db.mark_meeting_reminded(meeting_id, 'no_telegram')
                    continue
                if meeting_at is None:
                    await db.mark_meeting_reminded(meeting_id, 'invalid_date')
                    continue

                delta = meeting_at - now
                if delta < timedelta(0):
                    await db.mark_meeting_reminded(meeting_id, 'meeting_passed')
                    continue
                if delta > timedelta(hours=24):
                    continue

                text = (
                    f"Напоминание о встрече через 24 часа\n"
                    f"ФИО: {m.get('worker_name', '')}\n"
                    f"Дата и время: {m.get('date', '')}\n"
                )
                if m.get('note'):
                    text += f"Примечание: {m['note']}\n"
                try:
                    await bot.send_message(chat_id=m['telegram_id'], text=text)
                    await db.mark_meeting_reminded(meeting_id, now.isoformat())
                    logger.info("Напоминание о встрече отправлено worker=%s",
                                m.get('worker_id'))
                except Exception as e:
                    logger.warning("Не удалось отправить напоминание id=%s: %s",
                                   meeting_id, e)
        except Exception as e:
            logger.error("Ошибка проверки встреч: %s", e)

        await asyncio.sleep(30)


async def main():
    """Главная функция запуска бота"""
    bot = Bot(token=BOT_TOKEN)
    storage = SQLiteStorage(str(DB_PATH))
    dp = Dispatcher(storage=storage)

    # Rate limiting middleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=5, period=10.0))

    # Регистрация всех обработчиков
    WorkerForm = get_worker_form()
    register_commands(dp, WorkerForm)
    register_registration_handlers(dp, WorkerForm)
    register_document_handlers(dp, WorkerForm)
    register_confirmation_handlers(dp, WorkerForm)

    try:
        await on_startup(bot)
        bg_task = asyncio.create_task(check_rejected_workers(bot))
        meeting_task = asyncio.create_task(check_meeting_notifications(bot))
        try:
            await dp.start_polling(bot)
        finally:
            bg_task.cancel()
            meeting_task.cancel()
            for task in (bg_task, meeting_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    finally:
        await storage.close()
        await bot.session.close()
        console_print("\nБот остановлен.", 'yellow')


if __name__ == "__main__":
    asyncio.run(main())
