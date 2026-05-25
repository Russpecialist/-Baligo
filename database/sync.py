import asyncpg
import asyncio
import datetime
import pandas as pd
import gspread
from sqlalchemy.ext.asyncio import create_async_engine
from gspread_dataframe import set_with_dataframe, get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from config import host, port, user, password, namedb, table_names, spreadsheet_key
import warnings
import logging
from typing import Optional
import os

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsyncGoogleSheetsManager:
    """Менеджер для работы с Google Sheets"""

    def __init__(self):
        self.gc = None
        self.gs = None
        self.available = False
        self._init_google_sheets()

    def _init_google_sheets(self):
        """Инициализация подключения к Google Sheets"""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                'https://www.googleapis.com/auth/spreadsheets',
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive"
            ]

            credentials_paths = [
                'client_secret.json',
                '/app/client_secret.json',
                '/root/restobot/client_secret.json',
                os.path.join(os.path.dirname(__file__), 'client_secret.json')
            ]

            credentials = None
            for path in credentials_paths:
                try:
                    if os.path.exists(path):
                        credentials = ServiceAccountCredentials.from_json_keyfile_name(
                            path, scope)
                        logger.info(f"Credentials загружены из {path}")
                        break
                except Exception as e:
                    logger.warning(
                        f"Не удалось загрузить credentials из {path}: {e}")
                    continue

            if not credentials:
                logger.warning(
                    "Файл client_secret.json не найден — Google Sheets отключён")
                return

            self.gc = gspread.authorize(credentials)
            self.gs = self.gc.open_by_key(spreadsheet_key)
            self.available = True
            logger.info("Google Sheets подключен успешно")

        except Exception as e:
            logger.warning(
                f"Google Sheets недоступен: {e} — бот продолжит работу без синхронизации")
            self.available = False


class AsyncDatabaseSyncManager:
    """Менеджер для синхронизации данных между БД и Google Sheets"""

    def __init__(self):
        self.engine = None
        self.pool = None
        self.sheets_manager = AsyncGoogleSheetsManager()

    async def create_connections(self):
        """Создание соединений с БД"""
        conn_string = f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{namedb}'
        self.engine = create_async_engine(
            conn_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )

        self.pool = await asyncpg.create_pool(
            database=namedb,
            user=user,
            password=password,
            host=host,
            port=port,
            min_size=5,
            max_size=15
        )

        logger.info("Соединения с БД созданы")

    async def close_connections(self):
        """Закрытие соединений"""
        if self.engine:
            await self.engine.dispose()
        if self.pool:
            await self.pool.close()
        logger.info("Соединения с БД закрыты")

    async def export_table_to_sheets(self, table_name: str):
        """Экспорт данных из таблицы в Google Sheets"""
        if not self.sheets_manager.available:
            logger.warning("Google Sheets недоступен, пропускаем экспорт")
            return

        try:
            async with self.pool.acquire() as connection:
                query = f'SELECT * FROM {table_name};'
                rows = await connection.fetch(query)

                if rows:
                    df = pd.DataFrame([dict(row) for row in rows])
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._update_worksheet, table_name, df
                    )
                    logger.info(
                        f"Таблица {table_name} экспортирована в Google Sheets")
                else:
                    logger.warning(f"Таблица {table_name} пуста")

        except Exception as e:
            logger.error(f"Ошибка экспорта таблицы {table_name}: {e}")

    def _update_worksheet(self, table_name: str, df: pd.DataFrame):
        """Синхронное обновление worksheet"""
        try:
            worksheet = self.sheets_manager.gs.worksheet(table_name)
            worksheet.clear()
            set_with_dataframe(
                worksheet=worksheet,
                dataframe=df,
                include_index=False,
                include_column_header=True,
                resize=False
            )
        except Exception as e:
            logger.error(f"Ошибка обновления worksheet {table_name}: {e}")
            raise

    async def export_all_tables(self):
        """Экспорт всех таблиц в Google Sheets"""
        if not self.sheets_manager.available:
            logger.warning(
                "Google Sheets недоступен, пропускаем экспорт всех таблиц")
            return

        try:
            tasks = []
            for table_name in table_names:
                task = asyncio.create_task(
                    self.export_table_to_sheets(table_name))
                tasks.append(task)
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Все таблицы экспортированы")
        except Exception as e:
            logger.error(f"Ошибка экспорта всех таблиц: {e}")


# Глобальный экземпляр менеджера синхронизации
sync_manager = AsyncDatabaseSyncManager()


async def init_sync_manager():
    """Инициализация менеджера синхронизации"""
    await sync_manager.create_connections()
    logger.info("Менеджер синхронизации инициализирован")


async def close_sync_manager():
    """Закрытие соединений менеджера синхронизации"""
    await sync_manager.close_connections()
    logger.info("Менеджер синхронизации закрыт")


async def upload_to_sql():
    """Заглушка для совместимости"""
    logger.info("upload_to_sql вызван (не реализован)")


async def update_restaurant():
    """Обновление таблицы restaurant в Google Sheets"""
    if not sync_manager.pool:
        await sync_manager.create_connections()
    await sync_manager.export_table_to_sheets('restaurant')


async def sync_all_tables():
    """Синхронизация всех таблиц"""
    if not sync_manager.pool:
        await sync_manager.create_connections()
    await sync_manager.export_all_tables()


async def start_periodic_sync(interval_hours: int = 6):
    """Периодическая синхронизация"""
    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)
            logger.info("Начинается периодическая синхронизация")
            await sync_all_tables()
            logger.info("Периодическая синхронизация завершена")
        except asyncio.CancelledError:
            logger.info("Периодическая синхронизация отменена")
            break
        except Exception as e:
            logger.error(f"Ошибка в периодической синхронизации: {e}")
