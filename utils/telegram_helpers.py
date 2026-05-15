"""Утилиты для работы с Telegram API"""
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
import logging

logger = logging.getLogger(__name__)

async def get_chat_id_from_username(bot: Bot, username: str) -> Optional[int]:
    """
    Получение chat_id по username через Telegram Bot API
    
    Args:
        bot: Экземпляр бота
        username: Telegram username (с @ или без)
        
    Returns:
        chat_id пользователя или None, если не удалось получить
    """
    try:
        # Убираем @ если есть
        username = username.lstrip('@')
        
        if not username:
            logger.warning("Пустой username")
            return None
        
        # Пробуем получить информацию о пользователе через get_chat
        chat = await bot.get_chat(f"@{username}")
        
        if chat and chat.id:
            logger.info(f"Получен chat_id {chat.id} для username @{username}")
            return chat.id
        else:
            logger.warning(f"Не удалось получить chat_id для @{username}")
            return None
            
    except TelegramBadRequest as e:
        if "chat not found" in str(e).lower() or "user not found" in str(e).lower():
            logger.warning(f"Пользователь @{username} не найден")
        elif "username is invalid" in str(e).lower():
            logger.warning(f"Некорректный username: @{username}")
        else:
            logger.error(f"Ошибка Telegram API при получении chat_id для @{username}: {e}")
        return None
        
    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при получении chat_id для @{username}: {e}")
        return None
        
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении chat_id для @{username}: {e}")
        return None
