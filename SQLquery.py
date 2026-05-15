import asyncpg
import asyncio
import datetime
from config import namedb, user, password, host, port
from typing import Optional, List, Tuple, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер для работы с базой данных PostgreSQL"""
    
    def __init__(self):
        self.pool = None
        
    async def create_pool(self):
        """Создание пула соединений"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    database=namedb,
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    min_size=5,
                    max_size=20,
                    command_timeout=60
                )
                logger.info("Пул соединений с БД создан успешно")
            except Exception as e:
                logger.error(f"Ошибка создания пула соединений: {e}")
                raise
        return self.pool
    
    async def close_pool(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Пул соединений закрыт")
    
    async def execute_query(self, query: str, *args) -> None:
        """Выполнение INSERT/UPDATE/DELETE запросов"""
        pool = await self.create_pool()
        async with pool.acquire() as connection:
            try:
                await connection.execute(query, *args)
                logger.debug(f"Запрос выполнен: {query[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка выполнения запроса: {e}")
                raise
    
    async def fetch_query(self, query: str, *args) -> List[Any]:
        """Выполнение SELECT запросов с возвратом всех результатов"""
        pool = await self.create_pool()
        async with pool.acquire() as connection:
            try:
                result = await connection.fetch(query, *args)
                logger.debug(f"Запрос выполнен, получено {len(result)} записей")
                return result
            except Exception as e:
                logger.error(f"Ошибка выполнения запроса: {e}")
                raise
    
    async def fetchrow_query(self, query: str, *args) -> Optional[Any]:
        """Выполнение SELECT запросов с возвратом одной записи"""
        pool = await self.create_pool()
        async with pool.acquire() as connection:
            try:
                result = await connection.fetchrow(query, *args)
                logger.debug(f"Запрос выполнен, получена запись: {bool(result)}")
                return result
            except Exception as e:
                logger.error(f"Ошибка выполнения запроса: {e}")
                raise

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

async def add_new_user(message) -> None:
    """Добавление нового пользователя в таблицу users"""
    try:
        chat_id = message.chat.id
        user_name = '@' + str(message.chat.username) if message.chat.username else None
        date = datetime.datetime.now()
        first_name = message.chat.first_name
        last_name = message.chat.last_name
        role = 'user'
        status = 'active'
        
        query = '''
            INSERT INTO users (chat_id, first_name, last_name, username, date, role, status) 
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id) DO NOTHING;
        '''
        
        await db_manager.execute_query(
            query, chat_id, first_name, last_name, user_name, date, role, status
        )
        logger.info(f"Пользователь {chat_id} добавлен/обновлен в БД")
        
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя {message.chat.id}: {e}")
        # Не прерываем работу бота, если не удалось добавить пользователя

async def add_log_users(message) -> None:
    """Добавление действия пользователя в лог"""
    try:
        chat_id = message.chat.id
        username = '@' + str(message.chat.username) if message.chat.username else None
        message_text = message.text[:500] if message.text else None  # Ограничиваем длину
        first_name = message.chat.first_name
        last_name = message.chat.last_name
        date = datetime.datetime.now()
        
        query = '''
            INSERT INTO log_users (chat_id, username, first_name, last_name, message_text, date) 
            VALUES ($1, $2, $3, $4, $5, $6);
        '''
        
        await db_manager.execute_query(
            query, chat_id, username, first_name, last_name, message_text, date
        )
        logger.debug(f"Лог для пользователя {chat_id} добавлен")
        
    except Exception as e:
        logger.error(f"Ошибка добавления лога для {message.chat.id}: {e}")

async def get_user_role(message) -> List[Tuple[str, str]]:
    """Получение роли пользователя из таблицы users"""
    try:
        chat_id = message.chat.id
        query = '''SELECT role, status FROM users WHERE chat_id = $1;'''
        
        result = await db_manager.fetch_query(query, chat_id)
        
        if result:
            return [(row['role'], row['status']) for row in result]
        else:
            # Если пользователь не найден, возвращаем роль по умолчанию
            logger.warning(f"Пользователь {chat_id} не найден в БД")
            return [('user', 'active')]
            
    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя {message.chat.id}: {e}")
        return [('user', 'active')]  # Роль по умолчанию

async def change_role_sql(message, role: str) -> str:
    """Изменение роли пользователя"""
    try:
        user_id = message.text.strip()
        
        query = '''
            UPDATE users 
            SET role = $1 
            WHERE username = $2;
        '''
        
        await db_manager.execute_query(query, role, user_id)
        logger.info(f"Роль пользователя {user_id} изменена на {role}")
        return user_id
        
    except Exception as e:
        logger.error(f"Ошибка изменения роли пользователя {message.text}: {e}")
        raise

async def change_status_sql(status: str, chat_id: int) -> None:
    """Изменение статуса пользователя с повтором при ошибке"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            query = '''
                UPDATE users 
                SET status = $1 
                WHERE chat_id = $2;
            '''
            
            await db_manager.execute_query(query, status, chat_id)
            logger.info(f"Статус пользователя {chat_id} изменен на {status}")
            return
            
        except Exception as e:
            logger.error(f"Ошибка изменения статуса (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise

async def get_chat_id(username: str) -> Optional[int]:
    """Получение chat_id по username"""
    try:
        query = '''SELECT chat_id FROM users WHERE username = $1;'''
        
        result = await db_manager.fetchrow_query(query, username)
        
        if result:
            return result['chat_id']
        else:
            logger.warning(f"Пользователь {username} не найден")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка получения chat_id для {username}: {e}")
        return None

async def get_all_chat_id() -> List[Tuple[int]]:
    """Получение всех активных chat_id"""
    try:
        query = '''SELECT chat_id FROM users WHERE status = 'active';'''
        
        result = await db_manager.fetch_query(query)
        return [(row['chat_id'],) for row in result]
        
    except Exception as e:
        logger.error(f"Ошибка получения списка chat_id: {e}")
        return []

async def get_restaurant_names() -> List[Tuple[str]]:
    """Получение названий ресторанов"""
    try:
        query = '''SELECT DISTINCT restaurant_name FROM restaurant ORDER BY restaurant_name;'''
        
        result = await db_manager.fetch_query(query)
        return [(row['restaurant_name'],) for row in result]
        
    except Exception as e:
        logger.error(f"Ошибка получения названий ресторанов: {e}")
        return []

async def get_restaurant_info(restaurant: str) -> List[Any]:
    """Получение информации о ресторане"""
    try:
        query = '''
            SELECT DISTINCT * FROM restaurant 
            WHERE restaurant_name = $1;
        '''
        
        result = await db_manager.fetch_query(query, restaurant)
        return [tuple(row.values()) for row in result]
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о ресторане {restaurant}: {e}")
        return []

async def get_banquet_restaurants() -> List[Tuple[str]]:
    """Получение списка ресторанов с банкетными залами"""
    try:
        query = '''
            SELECT DISTINCT restaurant_name FROM restaurant 
            WHERE banquet_flg = 'Да' 
            ORDER BY restaurant_name;
        '''
        
        result = await db_manager.fetch_query(query)
        return [(row['restaurant_name'],) for row in result]
        
    except Exception as e:
        logger.error(f"Ошибка получения списка ресторанов с банкетами: {e}")
        return []

# Функция для инициализации БД (вызывать при старте приложения)
async def init_database():
    """Инициализация подключения к базе данных"""
    await db_manager.create_pool()
    logger.info("База данных инициализирована")

# Функция для закрытия соединений (вызывать при остановке приложения)
async def close_database():
    """Закрытие соединений с базой данных"""
    await db_manager.close_pool()
    logger.info("Соединения с базой данных закрыты")

async def get_regions():
    """Получение списка регионов"""
    try:
        query = '''
            SELECT DISTINCT region_nm
            FROM restaurant
            WHERE region_nm IS NOT NULL
            ORDER BY region_nm;
        '''
        result = await db_manager.fetch_query(query)
        return [row['region_nm'] for row in result]
    except Exception as e:
        logger.error(f"Ошибка получения списка регионов: {e}")
        return []


async def get_restaurants_by_region(region: str) -> list[str]:
    """Получение ресторанов по региону"""
    try:
        query = '''
            SELECT DISTINCT restaurant_name
            FROM restaurant
            WHERE region_nm = $1
              AND restaurant_name IS NOT NULL
            ORDER BY restaurant_name;
        '''
        result = await db_manager.fetch_query(query, region)
        # ВАЖНО: возвращаем список строк, не кортежей
        return [row['restaurant_name'] for row in result]
    except Exception as e:
        logger.error(f"Ошибка получения ресторанов региона {region}: {e}")
        return []


async def get_banquet_restaurants_by_region(region: str):
    """Получение банкетных ресторанов по региону"""
    try:
        query = '''
            SELECT DISTINCT restaurant_name
            FROM restaurant
            WHERE region_nm = $1
              AND banquet_flg = 'Да'
              AND restaurant_name IS NOT NULL
            ORDER BY restaurant_name;
        '''
        result = await db_manager.fetch_query(query, region)
        return [row['restaurant_name'] for row in result]
    except Exception as e:
        logger.error(f"Ошибка получения банкетных ресторанов региона {region}: {e}")
        return []
