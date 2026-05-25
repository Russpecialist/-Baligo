import asyncpg
import asyncio
import datetime
import os
from config import namedb, user, password, host, port
from typing import Optional, List, Tuple, Any, Dict
from database.activity import log_user_activity
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
                logger.debug(
                    f"Запрос выполнен, получено {len(result)} записей")
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
                logger.debug(
                    f"Запрос выполнен, получена запись: {bool(result)}")
                return result
            except Exception as e:
                logger.error(f"Ошибка выполнения запроса: {e}")
                raise


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

# ========== Функции для работы с пользователями ==========


async def add_new_user(message) -> None:
    """Добавление нового пользователя в таблицу users"""
    try:
        chat_id = message.chat.id
        user_name = '@' + \
            str(message.chat.username) if message.chat.username else None
        date = datetime.datetime.now()
        first_name = message.chat.first_name
        last_name = message.chat.last_name
        role = 'user'
        status = 'active'

        # Сначала проверяем, существует ли пользователь
        check_query = '''SELECT chat_id FROM users WHERE chat_id = $1;'''
        existing = await db_manager.fetchrow_query(check_query, chat_id)

        if existing:
            # Пользователь уже существует, обновляем информацию
            update_query = '''
                UPDATE users 
                SET first_name = $2, last_name = $3, username = $4, date = $5
                WHERE chat_id = $1;
            '''
            await db_manager.execute_query(
                update_query, chat_id, first_name, last_name, user_name, date
            )
            logger.info(f"Пользователь {chat_id} обновлен в БД")
        else:
            # Пользователь не существует, добавляем нового
            insert_query = '''
                INSERT INTO users (chat_id, first_name, last_name, username, date, role, status) 
                VALUES ($1, $2, $3, $4, $5, $6, $7);
            '''
            await db_manager.execute_query(
                insert_query, chat_id, first_name, last_name, user_name, date, role, status
            )
            logger.info(f"Пользователь {chat_id} добавлен в БД")

    except Exception as e:
        logger.error(f"Ошибка добавления пользователя {message.chat.id}: {e}")


async def add_log_users(message) -> None:
    """Добавление действия пользователя в лог"""
    try:
        chat_id = message.chat.id
        username = '@' + \
            str(message.chat.username) if message.chat.username else None
        message_text = message.text[:500] if message.text else None
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
            logger.warning(f"Пользователь {chat_id} не найден в БД")
            return [('user', 'active')]

    except Exception as e:
        logger.error(
            f"Ошибка получения роли пользователя {message.chat.id}: {e}")
        return [('user', 'active')]


async def get_user_role_by_chat_id(chat_id: int) -> Tuple[str, str]:
    """Получение роли пользователя по chat_id"""
    try:
        query = '''SELECT role, status FROM users WHERE chat_id = $1;'''

        result = await db_manager.fetchrow_query(query, chat_id)

        if result:
            return (result['role'], result['status'])
        else:
            return ('user', 'active')

    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя {chat_id}: {e}")
        return ('user', 'active')


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
            logger.error(
                f"Ошибка изменения статуса (попытка {attempt + 1}): {e}")
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


async def get_all_admin_chat_ids() -> List[int]:
    """Получение всех chat_id админов"""
    try:
        query = '''SELECT chat_id FROM users WHERE role = 'admin' AND status = 'active';'''

        result = await db_manager.fetch_query(query)
        return [row['chat_id'] for row in result]

    except Exception as e:
        logger.error(f"Ошибка получения списка админов: {e}")
        return []

# ========== Функции для работы с ресторанами ==========


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
        logger.error(
            f"Ошибка получения информации о ресторане {restaurant}: {e}")
        return []


async def get_restaurant_by_id(restaurant_id: int) -> Optional[Dict]:
    """Получение информации о ресторане по ID"""
    try:
        query = '''SELECT * FROM restaurant WHERE restaurant_id = $1;'''

        result = await db_manager.fetchrow_query(query, restaurant_id)

        if result:
            return dict(result)
        return None

    except Exception as e:
        logger.error(f"Ошибка получения ресторана {restaurant_id}: {e}")
        return None


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
        logger.error(
            f"Ошибка получения банкетных ресторанов региона {region}: {e}")
        return []


# Фиксированный порядок категорий партнёров Бали
CATEGORIES = [
    "🍽 Рестораны/Кафе/Бары",
    "🏨 Отели",
    "💆 СПА/Бани",
    "💪 GYM",
    "💅 Салоны красоты",
    "🛍 Магазины",
    "🏡 Аренда вилл и сервисы",
]

# Маппинг: метка кнопки → значение в БД
CATEGORY_LABEL_TO_DB = {
    "🍽 Рестораны/Кафе/Бары":   "Рестораны/Кафе/Бары",
    "🏨 Отели":                  "Отели",
    "💆 СПА/Бани":              "СПА/Бани",
    "💪 GYM":                   "GYM",
    "💅 Салоны красоты":         "Салоны красоты",
    "🛍 Магазины":              "Магазины",
    "🏡 Аренда вилл и сервисы": "Аренда вилл и сервисы",
}


async def get_categories_in_region(region: str) -> list:
    """Категории, у которых есть хотя бы один партнёр в данном районе.
    Возвращает список меток (с эмодзи) в порядке CATEGORIES."""
    try:
        query = """
            SELECT DISTINCT category
            FROM restaurant
            WHERE region_nm = $1
              AND category IS NOT NULL;
        """
        result = await db_manager.fetch_query(query, region)
        db_cats = {row['category'] for row in result}
        return [label for label in CATEGORIES
                if CATEGORY_LABEL_TO_DB.get(label) in db_cats]
    except Exception as e:
        logger.error(f"Ошибка получения категорий для региона {region}: {e}")
        return []


async def get_restaurants_by_region_and_category(region: str, category: str) -> list:
    """Получение партнёров по району и категории (category — значение из БД, без эмодзи)"""
    try:
        query = """
            SELECT DISTINCT restaurant_name
            FROM restaurant
            WHERE region_nm = $1
              AND category = $2
              AND restaurant_name IS NOT NULL
            ORDER BY restaurant_name;
        """
        result = await db_manager.fetch_query(query, region, category)
        return [row['restaurant_name'] for row in result]
    except Exception as e:
        logger.error(f"Ошибка получения партнёров {region}/{category}: {e}")
        return []

# ========== Функции для работы с user_restaurants ==========


async def get_user_restaurants(chat_id: int) -> List[Dict]:
    """Получение ресторанов пользователя"""
    try:
        query = '''
            SELECT ur.restaurant_id, r.restaurant_name, r.region_nm, r.address_nm
            FROM user_restaurants ur
            JOIN restaurant r ON ur.restaurant_id = r.restaurant_id
            WHERE ur.chat_id = $1
            ORDER BY r.restaurant_name;
        '''

        result = await db_manager.fetch_query(query, chat_id)
        return [dict(row) for row in result]

    except Exception as e:
        logger.error(
            f"Ошибка получения ресторанов пользователя {chat_id}: {e}")
        return []


async def add_user_restaurant(chat_id: int, restaurant_id: int) -> bool:
    """Добавление связи пользователя с рестораном"""
    try:
        # Сначала проверяем, существует ли уже такая связь
        check_query = '''
            SELECT chat_id, restaurant_id 
            FROM user_restaurants 
            WHERE chat_id = $1 AND restaurant_id = $2;
        '''
        existing = await db_manager.fetch_query(check_query, chat_id, restaurant_id)

        if existing:
            # Связь уже существует
            logger.info(
                f"Связь пользователя {chat_id} с рестораном {restaurant_id} уже существует")
            return True
        else:
            # Связи нет, добавляем новую
            query = '''
                INSERT INTO user_restaurants (chat_id, restaurant_id)
                VALUES ($1, $2);
            '''
            await db_manager.execute_query(query, chat_id, restaurant_id)
            logger.info(
                f"Связь пользователя {chat_id} с рестораном {restaurant_id} добавлена")
            return True

    except Exception as e:
        logger.error(f"Ошибка добавления связи: {e}")
        return False


async def remove_user_restaurant(chat_id: int, restaurant_id: int) -> bool:
    """Удаление связи пользователя с рестораном"""
    try:
        query = '''
            DELETE FROM user_restaurants
            WHERE chat_id = $1 AND restaurant_id = $2;
        '''

        await db_manager.execute_query(query, chat_id, restaurant_id)
        logger.info(
            f"Связь пользователя {chat_id} с рестораном {restaurant_id} удалена")
        return True

    except Exception as e:
        logger.error(f"Ошибка удаления связи: {e}")
        return False


async def get_restaurant_moderators(restaurant_id: int) -> List[Dict]:
    """Получение списка модераторов ресторана"""
    try:
        query = '''
            SELECT ur.chat_id, u.username, u.first_name, u.last_name
            FROM user_restaurants ur
            LEFT JOIN users u ON ur.chat_id = u.chat_id
            WHERE ur.restaurant_id = $1
            ORDER BY u.first_name, u.last_name, ur.chat_id;
        '''

        result = await db_manager.fetch_query(query, restaurant_id)
        return [dict(row) for row in result]

    except Exception as e:
        logger.error(
            f"Ошибка получения модераторов ресторана {restaurant_id}: {e}")
        return []


async def get_restaurant_id_by_name(restaurant_name: str) -> Optional[int]:
    """Получение restaurant_id по названию"""
    try:
        query = '''SELECT restaurant_id FROM restaurant WHERE restaurant_name = $1 LIMIT 1;'''

        result = await db_manager.fetchrow_query(query, restaurant_name)

        if result:
            return result['restaurant_id']
        return None

    except Exception as e:
        logger.error(
            f"Ошибка получения restaurant_id для {restaurant_name}: {e}")
        return None

# ========== Функции для работы с restaurant_approvals ==========


async def create_approval_request(
    restaurant_id: int,
    field_name: str,
    old_value: str,
    new_value: str,
    requested_by: int,
    temp_file_path: str = None
) -> Optional[int]:
    """Создание запроса на согласование изменения"""
    try:
        query = '''
            INSERT INTO restaurant_approvals 
            (restaurant_id, field_name, old_value, new_value, requested_by, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
            RETURNING id;
        '''

        pool = await db_manager.create_pool()
        async with pool.acquire() as connection:
            result = await connection.fetchrow(
                query, restaurant_id, field_name, old_value, new_value, requested_by
            )

            if result:
                approval_id = result['id']
                logger.info(f"Создан запрос на согласование {approval_id}")

                # Если это меню или банкет и есть временный файл, сохраняем путь к нему в new_value
                # (временно, до согласования)
                if field_name in ('menu', 'banquet') and temp_file_path:
                    # Обновляем new_value, чтобы хранить путь к временному файлу
                    update_query = '''
                        UPDATE restaurant_approvals 
                        SET new_value = $1 
                        WHERE id = $2;
                    '''
                    await connection.execute(update_query, temp_file_path, approval_id)

                return approval_id
            return None

    except Exception as e:
        logger.error(f"Ошибка создания запроса на согласование: {e}")
        return None


async def get_approval_request(approval_id: int) -> Optional[Dict]:
    """Получение запроса на согласование по ID"""
    try:
        query = '''
            SELECT 
                ra.id,
                ra.restaurant_id,
                ra.field_name,
                ra.old_value,
                ra.new_value,
                ra.status,
                ra.requested_by,
                ra.approved_by,
                ra.created_at,
                ra.updated_at,
                r.restaurant_name
            FROM restaurant_approvals ra
            JOIN restaurant r ON ra.restaurant_id = r.restaurant_id
            WHERE ra.id = $1;
        '''

        result = await db_manager.fetchrow_query(query, approval_id)

        if result:
            approval_dict = dict(result)
            # Убеждаемся, что created_at есть и правильно обработан
            if approval_dict.get('created_at') is None:
                logger.warning(
                    f"created_at is None for approval_id={approval_id}")
            return approval_dict
        return None

    except Exception as e:
        logger.error(f"Ошибка получения запроса {approval_id}: {e}")
        return None


async def get_pending_approvals() -> List[Dict]:
    """Получение всех ожидающих согласования запросов"""
    try:
        query = '''
            SELECT ra.*, r.restaurant_name
            FROM restaurant_approvals ra
            JOIN restaurant r ON ra.restaurant_id = r.restaurant_id
            WHERE ra.status = 'pending'
            ORDER BY ra.created_at DESC;
        '''

        result = await db_manager.fetch_query(query)
        return [dict(row) for row in result]

    except Exception as e:
        logger.error(f"Ошибка получения ожидающих запросов: {e}")
        return []


async def approve_request(approval_id: int, admin_chat_id: int) -> bool:
    """Подтверждение запроса на согласование"""
    try:
        query = '''
            UPDATE restaurant_approvals
            SET status = 'approved',
                approved_by = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND status = 'pending';
        '''

        pool = await db_manager.create_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(query, approval_id, admin_chat_id)

            if result == 'UPDATE 1':
                logger.info(
                    f"Запрос {approval_id} подтвержден админом {admin_chat_id}")
                # Применяем изменения
                await apply_approval(approval_id)
                return True
            return False

    except Exception as e:
        logger.error(f"Ошибка подтверждения запроса {approval_id}: {e}")
        return False


async def reject_request(approval_id: int, admin_chat_id: int) -> bool:
    """Отклонение запроса на согласование"""
    try:
        query = '''
            UPDATE restaurant_approvals
            SET status = 'rejected',
                approved_by = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND status = 'pending';
        '''

        pool = await db_manager.create_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(query, approval_id, admin_chat_id)

            if result == 'UPDATE 1':
                logger.info(
                    f"Запрос {approval_id} отклонен админом {admin_chat_id}")
                return True
            return False

    except Exception as e:
        logger.error(f"Ошибка отклонения запроса {approval_id}: {e}")
        return False


async def apply_approval(approval_id: int) -> bool:
    """Применение изменений к ресторану после подтверждения"""
    try:
        approval = await get_approval_request(approval_id)
        if not approval or approval['status'] != 'approved':
            return False

        restaurant_id = approval['restaurant_id']
        field_name = approval['field_name']
        new_value = approval['new_value']

        # Для меню изменения применяются вручную в handle_approve_callback
        # (перемещение файла из временной папки в rest_menu)
        if field_name == 'menu':
            # Обновляем только поле menu в БД на имя файла
            file_name = os.path.basename(
                new_value) if os.path.exists(new_value) else new_value
            query = '''
                UPDATE restaurant
                SET menu = $1
                WHERE restaurant_id = $2;
            '''
            await db_manager.execute_query(query, file_name, restaurant_id)
            logger.info(
                f"Изменения применены к ресторану {restaurant_id}, поле {field_name}")
            return True

        # Для банкетов изменения применяются вручную в handle_approve_callback
        # (перемещение файла из временной папки в rest_menu/{restaurant_name}/Банкет)
        # Банкеты не хранятся в БД, только как файлы
        if field_name == 'banquet':
            logger.info(
                f"Изменения банкета применены к ресторану {restaurant_id} (файл уже перемещен)")
            return True

        # Для других полей обновляем как обычно
        query = f'''
            UPDATE restaurant
            SET {field_name} = $1
            WHERE restaurant_id = $2;
        '''

        await db_manager.execute_query(query, new_value, restaurant_id)
        logger.info(
            f"Изменения применены к ресторану {restaurant_id}, поле {field_name}")
        return True

    except Exception as e:
        logger.error(f"Ошибка применения изменений {approval_id}: {e}")
        return False


async def get_user_approvals(chat_id: int) -> List[Dict]:
    """Получение всех запросов пользователя"""
    try:
        query = '''
            SELECT ra.*, r.restaurant_name
            FROM restaurant_approvals ra
            JOIN restaurant r ON ra.restaurant_id = r.restaurant_id
            WHERE ra.requested_by = $1
            ORDER BY ra.created_at DESC;
        '''

        result = await db_manager.fetch_query(query, chat_id)
        return [dict(row) for row in result]

    except Exception as e:
        logger.error(f"Ошибка получения запросов пользователя {chat_id}: {e}")
        return []

# ========== Функции для управления ресторанами ==========


async def get_next_restaurant_id() -> int:
    """Получение следующего restaurant_id"""
    try:
        query = '''SELECT COALESCE(MAX(restaurant_id), 0) + 1 as next_id FROM restaurant;'''
        result = await db_manager.fetchrow_query(query)
        if result:
            return result['next_id']
        return 1
    except Exception as e:
        logger.error(f"Ошибка получения следующего restaurant_id: {e}")
        return 1


async def create_restaurant(
    restaurant_name: str,
    address_nm: str,
    reservation: str,
    delivery: str,
    region_nm: str,
    category: str = None
) -> Optional[int]:
    """Создание нового партнёра"""
    try:
        restaurant_id = await get_next_restaurant_id()
        query = '''
            INSERT INTO restaurant 
            (restaurant_id, restaurant_name, address_nm, reservation, delivery, region_nm, category, menu, promo, banquet_flg)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 0, NULL, NULL)
            RETURNING restaurant_id;
        '''

        pool = await db_manager.create_pool()
        async with pool.acquire() as connection:
            result = await connection.fetchrow(
                query, restaurant_id, restaurant_name, address_nm, reservation, delivery, region_nm, category
            )

            if result:
                logger.info(
                    f"Создан ресторан {restaurant_id}: {restaurant_name}")
                return result['restaurant_id']
            return None

    except Exception as e:
        logger.error(f"Ошибка создания ресторана: {e}")
        return None


async def get_all_restaurants() -> List[Dict]:
    """Получение списка всех ресторанов"""
    try:
        query = '''
            SELECT restaurant_id, restaurant_name, region_nm, address_nm
            FROM restaurant
            ORDER BY restaurant_name;
        '''

        result = await db_manager.fetch_query(query)
        return [dict(row) for row in result]

    except Exception as e:
        logger.error(f"Ошибка получения списка ресторанов: {e}")
        return []


async def update_restaurant(restaurant_id: int, **fields) -> bool:
    """Обновление полей ресторана"""
    try:
        if not fields:
            return False

        # Формируем SET часть запроса динамически
        set_parts = []
        values = []
        param_num = 1

        allowed_fields = ['restaurant_name', 'address_nm', 'reservation',
                          'delivery', 'region_nm', 'menu', 'promo', 'banquet_flg']

        for field, value in fields.items():
            if field in allowed_fields:
                set_parts.append(f"{field} = ${param_num}")
                values.append(value)
                param_num += 1

        if not set_parts:
            return False

        values.append(restaurant_id)
        query = f'''
            UPDATE restaurant
            SET {', '.join(set_parts)}
            WHERE restaurant_id = ${param_num};
        '''

        await db_manager.execute_query(query, *values)
        logger.info(
            f"Ресторан {restaurant_id} обновлен: {', '.join(fields.keys())}")
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления ресторана {restaurant_id}: {e}")
        return False


async def delete_restaurant(restaurant_id: int) -> bool:
    """Удаление ресторана"""
    try:
        query = '''DELETE FROM restaurant WHERE restaurant_id = $1;'''
        await db_manager.execute_query(query, restaurant_id)
        logger.info(f"Ресторан {restaurant_id} удален")
        return True

    except Exception as e:
        logger.error(f"Ошибка удаления ресторана {restaurant_id}: {e}")
        return False

# ========== Функции для работы с акциями и событиями ==========


async def get_promotions(restaurant_id: int, status: str = 'approved') -> List[Dict]:
    """Получение списка акций ресторана"""
    try:
        query = '''
            SELECT id, restaurant_id, title, description, photo_file_id, photo_path, status, created_at, updated_at
            FROM promotions
            WHERE restaurant_id = $1 AND status = $2
            ORDER BY created_at DESC;
        '''
        result = await db_manager.fetch_query(query, restaurant_id, status)
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(
            f"Ошибка получения акций для ресторана {restaurant_id}: {e}")
        return []


async def get_events(restaurant_id: int, status: str = 'approved') -> List[Dict]:
    """Получение списка событий ресторана"""
    try:
        query = '''
            SELECT id, restaurant_id, title, description, photo_file_id, photo_path, status, created_at, updated_at
            FROM events
            WHERE restaurant_id = $1 AND status = $2
            ORDER BY created_at DESC;
        '''
        result = await db_manager.fetch_query(query, restaurant_id, status)
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(
            f"Ошибка получения событий для ресторана {restaurant_id}: {e}")
        return []


async def get_promotion_by_id(promotion_id: int) -> Optional[Dict]:
    """Получение акции по ID"""
    try:
        query = '''
            SELECT id, restaurant_id, title, description, photo_file_id, photo_path, status, created_at, updated_at
            FROM promotions
            WHERE id = $1;
        '''
        result = await db_manager.fetchrow_query(query, promotion_id)
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Ошибка получения акции {promotion_id}: {e}")
        return None


async def get_event_by_id(event_id: int) -> Optional[Dict]:
    """Получение события по ID"""
    try:
        query = '''
            SELECT id, restaurant_id, title, description, photo_file_id, photo_path, status, created_at, updated_at
            FROM events
            WHERE id = $1;
        '''
        result = await db_manager.fetchrow_query(query, event_id)
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Ошибка получения события {event_id}: {e}")
        return None


async def create_promotion_event_approval(
    restaurant_id: int,
    type: str,  # 'promotion' или 'event'
    action: str,  # 'create', 'update', 'delete'
    requested_by: int,
    title: str = None,
    description: str = None,
    photo_file_id: str = None,
    photo_path: str = None,
    item_id: int = None,
    old_data: dict = None
) -> Optional[int]:
    """Создание запроса на согласование изменения акции или события"""
    try:
        import json
        old_data_json = json.dumps(old_data) if old_data else None

        query = '''
            INSERT INTO promotion_event_approvals 
            (restaurant_id, type, action, item_id, title, description, photo_file_id, photo_path, old_data, requested_by, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending')
            RETURNING id;
        '''
        result = await db_manager.fetchrow_query(
            query, restaurant_id, type, action, item_id, title, description,
            photo_file_id, photo_path, old_data_json, requested_by
        )
        return result['id'] if result else None
    except Exception as e:
        logger.error(f"Ошибка создания запроса на согласование: {e}")
        return None


async def get_promotion_event_approval(approval_id: int) -> Optional[Dict]:
    """Получение запроса на согласование по ID"""
    try:
        query = '''
            SELECT pea.*, r.restaurant_name
            FROM promotion_event_approvals pea
            JOIN restaurant r ON pea.restaurant_id = r.restaurant_id
            WHERE pea.id = $1;
        '''
        result = await db_manager.fetchrow_query(query, approval_id)
        if result:
            import json
            data = dict(result)
            if data.get('old_data'):
                try:
                    data['old_data'] = json.loads(data['old_data'])
                except:
                    pass
            return data
        return None
    except Exception as e:
        logger.error(
            f"Ошибка получения запроса на согласование {approval_id}: {e}")
        return None


async def get_pending_promotion_event_approvals() -> List[Dict]:
    """Получение всех ожидающих согласования запросов"""
    try:
        query = '''
            SELECT pea.*, r.restaurant_name
            FROM promotion_event_approvals pea
            JOIN restaurant r ON pea.restaurant_id = r.restaurant_id
            WHERE pea.status = 'pending'
            ORDER BY pea.created_at DESC;
        '''
        result = await db_manager.fetch_query(query)
        approvals = []
        for row in result:
            import json
            data = dict(row)
            if data.get('old_data'):
                try:
                    data['old_data'] = json.loads(data['old_data'])
                except:
                    pass
            approvals.append(data)
        return approvals
    except Exception as e:
        logger.error(f"Ошибка получения ожидающих согласования запросов: {e}")
        return []


async def approve_promotion_event(approval_id: int, approved_by: int) -> bool:
    """Одобрение изменения акции или события"""
    try:
        approval = await get_promotion_event_approval(approval_id)
        if not approval:
            return False

        if approval['action'] == 'create':
            # Создаем новую акцию или событие
            if approval['type'] == 'promotion':
                query = '''
                    INSERT INTO promotions (restaurant_id, title, description, photo_file_id, photo_path, status)
                    VALUES ($1, $2, $3, $4, $5, 'approved')
                    RETURNING id;
                '''
            else:  # event
                query = '''
                    INSERT INTO events (restaurant_id, title, description, photo_file_id, photo_path, status)
                    VALUES ($1, $2, $3, $4, $5, 'approved')
                    RETURNING id;
                '''
            await db_manager.fetchrow_query(
                query, approval['restaurant_id'], approval['title'],
                approval['description'], approval['photo_file_id'], approval['photo_path']
            )
        elif approval['action'] == 'update':
            # Обновляем существующую акцию или событие
            if approval['type'] == 'promotion':
                query = '''
                    UPDATE promotions
                    SET title = $2, description = $3, photo_file_id = $4, photo_path = $5, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1;
                '''
            else:  # event
                query = '''
                    UPDATE events
                    SET title = $2, description = $3, photo_file_id = $4, photo_path = $5, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1;
                '''
            await db_manager.execute_query(
                query, approval['item_id'], approval['title'],
                approval['description'], approval['photo_file_id'], approval['photo_path']
            )
        elif approval['action'] == 'delete':
            # Удаляем акцию или событие
            if approval['type'] == 'promotion':
                query = 'DELETE FROM promotions WHERE id = $1;'
            else:  # event
                query = 'DELETE FROM events WHERE id = $1;'
            await db_manager.execute_query(query, approval['item_id'])

        # Обновляем статус запроса на согласование
        update_query = '''
            UPDATE promotion_event_approvals
            SET status = 'approved', approved_by = $2, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1;
        '''
        await db_manager.execute_query(update_query, approval_id, approved_by)
        return True
    except Exception as e:
        logger.error(f"Ошибка одобрения изменения: {e}")
        return False


async def reject_promotion_event(approval_id: int, approved_by: int) -> bool:
    """Отклонение изменения акции или события"""
    try:
        query = '''
            UPDATE promotion_event_approvals
            SET status = 'rejected', approved_by = $2, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1;
        '''
        await db_manager.execute_query(query, approval_id, approved_by)
        return True
    except Exception as e:
        logger.error(f"Ошибка отклонения изменения: {e}")
        return False

# ========== Инициализация и закрытие ==========


async def init_database():
    """Инициализация подключения к базе данных"""
    await db_manager.create_pool()
    logger.info("База данных инициализирована")


async def close_database():
    """Закрытие соединений с базой данных"""
    await db_manager.close_pool()
    logger.info("Соединения с базой данных закрыты")
