"""Middleware для проверки ролей пользователей"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.queries import get_user_role_by_chat_id
import logging

logger = logging.getLogger(__name__)

class RoleCheckMiddleware(BaseMiddleware):
    """Middleware для проверки ролей пользователей"""
    
    def __init__(self):
        pass
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Получаем chat_id из события
            if hasattr(event, 'from_user') and event.from_user:
                chat_id = event.from_user.id
                role, status = await get_user_role_by_chat_id(chat_id)
                
                # Сохраняем роль в data для использования в handlers
                data['user_role'] = role
                data['user_status'] = status
        except Exception as e:
            logger.error(f"Ошибка в RoleCheckMiddleware: {e}", exc_info=True)
        
        return await handler(event, data)
