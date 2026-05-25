# database/activity.py
import logging
from .queries import db_manager

logger = logging.getLogger(__name__)


async def log_user_activity(
    chat_id: int,
    username: str = None,
    first_name: str = None,
    action: str = None,
    region_nm: str = None,
    category: str = None,
    partner_name: str = None
) -> None:
    """Логирование активности пользователя"""
    try:
        query = '''
            INSERT INTO user_activity 
            (chat_id, username, first_name, action, region_nm, category, partner_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        '''
        await db_manager.execute_query(
            query, chat_id, username, first_name, action, region_nm, category, partner_name
        )
    except Exception as e:
        logger.error(f"Ошибка логирования активности: {e}")
