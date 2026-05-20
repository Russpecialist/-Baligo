"""Главный файл для запуска Telegram бота"""
import asyncio
import signal
import sys
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import token_id
from database.queries import init_database, close_database
from database.sync import init_sync_manager, close_sync_manager
from handlers.common import register_common_handlers, register_unhandled_handler
from handlers.user import register_user_handlers
from handlers.admin import register_admin_handlers
from handlers.restaurant import register_restaurant_handlers
from handlers.approval import register_approval_handlers
from handlers.promotions_events import register_promotions_events_handlers
from middleware.role_check import RoleCheckMiddleware
from utils.helpers import log_error
from handlers.ai_assistant import register_ai_handlers
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create bot and dispatcher
bot = Bot(token=token_id)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация middleware
dp.message.middleware(RoleCheckMiddleware())
dp.callback_query.middleware(RoleCheckMiddleware())

# Регистрация handlers
logger.info("Начинаем регистрацию handlers...")
register_common_handlers(dp, bot)
logger.info(f"После common: {len(dp.message.handlers)} handlers")
register_user_handlers(dp, bot)
logger.info(f"После user: {len(dp.message.handlers)} handlers")
register_admin_handlers(dp, bot)
logger.info(f"После admin: {len(dp.message.handlers)} handlers")
register_restaurant_handlers(dp, bot)
logger.info(f"После restaurant: {len(dp.message.handlers)} handlers")
register_approval_handlers(dp, bot)
logger.info(f"После approval: {len(dp.message.handlers)} handlers")
register_promotions_events_handlers(dp, bot)
logger.info(f"После promotions_events: {len(dp.message.handlers)} handlers")
register_unhandled_handler(dp, bot)
logger.info(f"После unhandled: {len(dp.message.handlers)} handlers")

register_ai_handlers(dp, bot)


async def shutdown_handler():
    """Обработчик для корректного завершения работы"""
    logger.info("Получен сигнал завершения, останавливаем бота...")
    try:
        await close_database()
        await close_sync_manager()
        logger.info("Все соединения закрыты")
    except Exception as e:
        logger.error(f"Ошибка при завершении: {e}")


async def main():
    """Основная функция для запуска бота"""
    # Обработка сигналов завершения
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}")
        loop = asyncio.get_event_loop()
        loop.create_task(shutdown_handler())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Инициализация подключений к БД
        logger.info("Инициализация подключений к БД...")
        await init_database()
        await init_sync_manager()

        # Предварительное кэширование всех PDF файлов (в фоновом режиме)
        from config import MENU_PATH
        from utils.pdf_converter import pre_cache_all_pdfs

        async def background_cache():
            """Фоновая задача для предварительного кэширования"""
            try:
                logger.info(
                    "Начинаем предварительное кэширование PDF файлов...")
                cache_stats = await pre_cache_all_pdfs(MENU_PATH)
                logger.info(
                    f"Предварительное кэширование завершено: {cache_stats['cached']}/{cache_stats['total']} файлов, {cache_stats['errors']} ошибок")
            except Exception as e:
                logger.error(f"Ошибка при предварительном кэшировании: {e}")

        # Запускаем кэширование в фоне, не блокируя запуск бота
        asyncio.create_task(background_cache())

        # Настройка логирования для aiogram
        logging.getLogger('aiogram.event').setLevel(logging.INFO)
        logging.getLogger('aiogram.dispatcher').setLevel(logging.INFO)

        logger.info("Бот успешно запущен и готов к работе!")
        logger.info(
            f"Зарегистрировано handlers: {len(dp.message.handlers)} message handlers")
        logger.info(
            f"Зарегистрировано callback handlers: {len(dp.callback_query.handlers)} callback handlers")

        # Выводим список всех зарегистрированных обработчиков для отладки
        for i, handler in enumerate(dp.message.handlers):
            logger.info(f"Handler {i+1}: {handler}")

        # Запуск бота
        await dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=['message', 'callback_query']
        )

    except KeyboardInterrupt:
        logger.info("Получено прерывание с клавиатуры")
    except Exception as e:
        await log_error(e, "polling")
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise
    finally:
        await shutdown_handler()

if __name__ == '__main__':
    asyncio.run(main())
