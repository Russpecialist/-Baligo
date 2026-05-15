"""Вспомогательные функции"""
import logging
import traceback
import datetime
import os
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

async def log_error(error: Exception, context: str = "general") -> None:
    """Асинхронная функция для логирования ошибок"""
    traceback_error_string = traceback.format_exc()
    filename = f"error_{context}.log"
    
    try:
        with open(filename, "a", encoding='utf-8') as myfile:
            date = str(datetime.datetime.now())
            myfile.write(
                f"\r\n\r\n{date}\r\n<<ERROR {context} start>>\r\n"
                f"{traceback_error_string}\r\n{str(error)}\r\n<<ERROR {context} finish>>"
            )
    except Exception as e:
        logger.error(f"Ошибка записи в лог файл: {e}")

def format_approval_message(approval: dict) -> str:
    """Форматирование сообщения о запросе на согласование"""
    restaurant_name = approval.get('restaurant_name', 'Неизвестный ресторан')
    field_name = approval.get('field_name', '')
    old_value = approval.get('old_value', 'Не указано')
    new_value = approval.get('new_value', 'Не указано')
    created_at_raw = approval.get('created_at')
    
    # Форматируем дату
    if created_at_raw:
        if isinstance(created_at_raw, datetime.datetime):
            created_at = created_at_raw.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(created_at_raw, str):
            created_at = created_at_raw
        else:
            created_at = str(created_at_raw)
    else:
        created_at = 'Не указано'
    
    field_names_ru = {
        'restaurant_name': 'Название ресторана',
        'menu': 'Меню',
        'banquet': 'Банкет',
        'reservation': 'Бронирование',
        'delivery': 'Доставка',
        'region_nm': 'Регион',
        'address_nm': 'Адрес'
    }
    
    field_display = field_names_ru.get(field_name, field_name)
    
    message = f"""
📋 Запрос на изменение информации о ресторане

🏪 Ресторан: {restaurant_name}
📝 Поле: {field_display}
🆔 ID запроса: {approval.get('id')}

📄 Текущее значение:
{old_value[:500]}

✨ Новое значение:
{new_value[:500]}

🕐 Создан: {created_at}
"""
    return message

def format_approval_status_message(approval: dict) -> str:
    """Форматирование сообщения о статусе заявки"""
    restaurant_name = approval.get('restaurant_name', 'Неизвестный ресторан')
    field_name = approval.get('field_name', '')
    status = approval.get('status', 'pending')
    created_at = approval.get('created_at', '')
    updated_at = approval.get('updated_at', '')
    
    field_names_ru = {
        'restaurant_name': 'Название ресторана',
        'menu': 'Меню',
        'banquet': 'Банкет',
        'reservation': 'Бронирование',
        'delivery': 'Доставка',
        'region_nm': 'Регион',
        'address_nm': 'Адрес'
    }
    
    field_display = field_names_ru.get(field_name, field_name)
    
    status_emoji = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    status_text = {
        'pending': 'Ожидает согласования',
        'approved': 'Подтверждено',
        'rejected': 'Отклонено'
    }
    
    message = f"""
{status_emoji.get(status, '❓')} {status_text.get(status, status)}

🏪 Ресторан: {restaurant_name}
📝 Поле: {field_display}
🆔 ID: {approval.get('id')}
🕐 Создан: {created_at}
"""
    
    if updated_at:
        message += f"🕐 Обновлен: {updated_at}\n"
    
    return message

async def send_menu_approval_message(
    bot: Bot,
    admin_chat_id: int,
    approval: dict,
    old_file_path: Optional[str],
    new_file_path: str
):
    """Отправка сообщения о запросе на согласование меню с файлами"""
    from utils.keyboards import get_approval_keyboard
    from config import MENU_PATH
    
    restaurant_name = approval.get('restaurant_name', 'Неизвестный ресторан')
    approval_id = approval.get('id')
    created_at_raw = approval.get('created_at')
    
    # Форматируем дату
    if created_at_raw:
        if isinstance(created_at_raw, datetime.datetime):
            created_at = created_at_raw.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(created_at_raw, str):
            created_at = created_at_raw
        else:
            created_at = str(created_at_raw)
    else:
        created_at = 'Не указано'
    
    old_value = approval.get('old_value', 'Нет файла')
    new_value = approval.get('new_value', 'Неизвестно')
    
    # Формируем текстовое сообщение
    msg_text = f"""
📋 Запрос на изменение информации о ресторане

🏪 Ресторан: {restaurant_name}
📝 Поле: Меню
🆔 ID запроса: {approval_id}

📄 Текущее значение:
{old_value}

✨ Новое значение:
{new_value}

🕐 Создан: {created_at}
"""
    
    # Отправляем текстовое сообщение с кнопками
    markup = get_approval_keyboard(approval_id)
    await bot.send_message(admin_chat_id, msg_text, reply_markup=markup)
    
    # Отправляем старый файл (если есть)
    if old_file_path and os.path.exists(old_file_path):
        try:
            from utils.pdf_converter import load_telegram_document_file_id, save_telegram_document_file_id
            
            # Пытаемся использовать кэшированный file_id
            cached_file_id = load_telegram_document_file_id(old_file_path)
            
            if cached_file_id:
                try:
                    sent_message = await bot.send_document(
                        admin_chat_id,
                        cached_file_id,
                        caption=f"📄 Старое меню: {os.path.basename(old_file_path)}"
                    )
                    logger.debug(f"Использован кэшированный file_id для старого файла: {old_file_path}")
                    # Сохраняем file_id из ответа, чтобы убедиться, что он актуален
                    if sent_message.document:
                        save_telegram_document_file_id(old_file_path, sent_message.document.file_id)
                except Exception as e:
                    # Если file_id недействителен, отправляем файл заново
                    logger.warning(f"file_id для старого файла недействителен, отправляем файл: {e}")
                    old_file = FSInputFile(old_file_path)
                    sent_message = await bot.send_document(
                        admin_chat_id,
                        old_file,
                        caption=f"📄 Старое меню: {os.path.basename(old_file_path)}"
                    )
                    # Сохраняем file_id из ответа
                    if sent_message.document:
                        save_telegram_document_file_id(old_file_path, sent_message.document.file_id)
            else:
                # Отправляем файл и сохраняем file_id
                old_file = FSInputFile(old_file_path)
                sent_message = await bot.send_document(
                    admin_chat_id,
                    old_file,
                    caption=f"📄 Старое меню: {os.path.basename(old_file_path)}"
                )
                # Сохраняем file_id из ответа
                if sent_message.document:
                    save_telegram_document_file_id(old_file_path, sent_message.document.file_id)
        except Exception as e:
            logger.error(f"Ошибка отправки старого файла: {e}")
    else:
        # Если старого файла нет, отправляем сообщение
        await bot.send_message(
            admin_chat_id,
            "📄 Старое меню: файл отсутствует"
        )
    
    # Отправляем новый файл (из временной папки)
    if new_file_path and os.path.exists(new_file_path):
        try:
            from utils.pdf_converter import load_telegram_document_file_id, save_telegram_document_file_id
            
            # Пытаемся использовать кэшированный file_id
            cached_file_id = load_telegram_document_file_id(new_file_path)
            
            if cached_file_id:
                try:
                    sent_message = await bot.send_document(
                        admin_chat_id,
                        cached_file_id,
                        caption=f"✨ Новое меню: {os.path.basename(new_file_path)}"
                    )
                    logger.debug(f"Использован кэшированный file_id для нового файла: {new_file_path}")
                    # Сохраняем file_id из ответа, чтобы убедиться, что он актуален
                    if sent_message.document:
                        save_telegram_document_file_id(new_file_path, sent_message.document.file_id)
                except Exception as e:
                    # Если file_id недействителен, отправляем файл заново
                    logger.warning(f"file_id для нового файла недействителен, отправляем файл: {e}")
                    new_file = FSInputFile(new_file_path)
                    sent_message = await bot.send_document(
                        admin_chat_id,
                        new_file,
                        caption=f"✨ Новое меню: {os.path.basename(new_file_path)}"
                    )
                    # Сохраняем file_id из ответа
                    if sent_message.document:
                        save_telegram_document_file_id(new_file_path, sent_message.document.file_id)
            else:
                # Отправляем файл и сохраняем file_id
                new_file = FSInputFile(new_file_path)
                sent_message = await bot.send_document(
                    admin_chat_id,
                    new_file,
                    caption=f"✨ Новое меню: {os.path.basename(new_file_path)}"
                )
                # Сохраняем file_id из ответа
                if sent_message.document:
                    save_telegram_document_file_id(new_file_path, sent_message.document.file_id)
        except Exception as e:
            logger.error(f"Ошибка отправки нового файла: {e}")

def format_promotion_event_approval_message(approval: dict) -> str:
    """Форматирование сообщения о запросе на согласование акции или события"""
    restaurant_name = approval.get('restaurant_name', 'Неизвестный ресторан')
    type_name = approval.get('type', '')  # 'promotion' или 'event'
    action = approval.get('action', '')  # 'create', 'update', 'delete'
    title = approval.get('title', 'Не указано')
    description = approval.get('description', 'Не указано')
    created_at_raw = approval.get('created_at')
    
    # Форматируем дату
    if created_at_raw:
        if isinstance(created_at_raw, datetime.datetime):
            created_at = created_at_raw.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(created_at_raw, str):
            created_at = created_at_raw
        else:
            created_at = str(created_at_raw)
    else:
        created_at = 'Не указано'
    
    type_names_ru = {
        'promotion': 'Акция',
        'event': 'Событие'
    }
    
    action_names_ru = {
        'create': 'Создание',
        'update': 'Обновление',
        'delete': 'Удаление'
    }
    
    type_display = type_names_ru.get(type_name, type_name)
    action_display = action_names_ru.get(action, action)
    
    message = f"""
📋 Запрос на {action_display.lower()} {type_display.lower()}

🏪 Ресторан: {restaurant_name}
📝 Тип: {type_display}
🔄 Действие: {action_display}
🆔 ID запроса: {approval.get('id')}

📄 Название: {title}
📝 Описание: {description[:500] if description else 'Не указано'}

🕐 Создан: {created_at}
"""
    return message

def format_promotion_event_newsletter_proposal(approval: dict) -> str:
    """Форматирование предложения для рассылки после согласования акции/события"""
    restaurant_name = approval.get('restaurant_name', 'ресторан')
    type_name = approval.get('type', '')  # 'promotion' или 'event'
    
    type_names_ru = {
        'promotion': 'акция',
        'event': 'событие'
    }
    
    type_display = type_names_ru.get(type_name, 'новость')
    
    # Формат: "В ресторане {название} новое событие:" или "В ресторане {название} новая акция:"
    if type_name == 'event':
        message = f"В ресторане {restaurant_name} новое событие:"
    else:
        message = f"В ресторане {restaurant_name} новая акция:"
    
    return message

def format_newsletter_proposal(approval: dict) -> str:
    """Форматирование предложения для рассылки после согласования"""
    restaurant_name = approval.get('restaurant_name', 'ресторан')
    field_name = approval.get('field_name', '')
    
    field_names_ru = {
        'restaurant_name': 'название',
        'menu': 'меню',
        'reservation': 'информация о бронировании',
        'delivery': 'информация о доставке',
        'region_nm': 'регион',
        'address_nm': 'адрес'
    }
    
    field_display = field_names_ru.get(field_name, 'информация')
    
    # Правильное согласование в зависимости от рода слова
    if field_name == 'menu':
        # "меню" - средний род
        message = f"🍽 В ресторане «{restaurant_name}» обновилось меню!\n\n✨ Приглашаем вас ознакомиться с новыми блюдами и акциями."
    elif field_name in ['reservation', 'delivery']:
        # "информация" - женский род
        message = f"📋 В ресторане «{restaurant_name}» обновилась {field_display}.\n\n✨ Приглашаем вас ознакомиться с изменениями!"
    elif field_name in ['restaurant_name', 'address_nm', 'region_nm']:
        # "название", "адрес", "регион" - средний/мужской род
        if field_name == 'restaurant_name':
            message = f"🏪 Ресторан «{restaurant_name}» обновил своё название.\n\n✨ Приглашаем вас ознакомиться с изменениями!"
        elif field_name == 'address_nm':
            message = f"📍 В ресторане «{restaurant_name}» обновился адрес.\n\n✨ Приглашаем вас ознакомиться с изменениями!"
        else:  # region_nm
            message = f"🌍 В ресторане «{restaurant_name}» обновился регион.\n\n✨ Приглашаем вас ознакомиться с изменениями!"
    else:
        message = f"📋 В ресторане «{restaurant_name}» обновилась {field_display}.\n\n✨ Приглашаем вас ознакомиться с изменениями!"
    
    return message

def split_text_for_caption(text: str, max_length: int = 1024) -> tuple[str, str]:
    """
    Разбивает текст на две части: для подписи к фото и остальной текст
    
    Args:
        text: Текст для разбиения
        max_length: Максимальная длина подписи (по умолчанию 1024 для Telegram)
    
    Returns:
        tuple: (caption_text, remaining_text)
    """
    if not text:
        return "", ""
    
    if len(text) <= max_length:
        return text, ""
    
    # Пытаемся разбить по предложениям (по точке, восклицательному или вопросительному знаку)
    # Ищем последнее предложение, которое помещается в max_length
    last_sentence_end = -1
    for i in range(max_length - 1, max(0, max_length - 200), -1):  # Ищем в последних 200 символах
        if text[i] in '.!?\n':
            last_sentence_end = i + 1
            break
    
    # Если не нашли подходящее место, разбиваем по пробелам
    if last_sentence_end == -1:
        last_space = text.rfind(' ', 0, max_length)
        if last_space > max_length * 0.7:  # Если пробел не слишком близко к началу
            last_sentence_end = last_space
        else:
            # Если ничего не подходит, просто обрезаем
            last_sentence_end = max_length
    
    caption_text = text[:last_sentence_end].strip()
    remaining_text = text[last_sentence_end:].strip()
    
    return caption_text, remaining_text

def split_text_into_messages(text: str, max_length: int = 4096) -> list[str]:
    """
    Разбивает длинный текст на несколько сообщений
    
    Args:
        text: Текст для разбиения
        max_length: Максимальная длина одного сообщения (по умолчанию 4096 для Telegram)
    
    Returns:
        list: Список текстов для отправки
    """
    if not text:
        return []
    
    if len(text) <= max_length:
        return [text]
    
    messages = []
    remaining = text
    
    while len(remaining) > max_length:
        # Пытаемся разбить по предложениям
        last_sentence_end = -1
        for i in range(max_length - 1, max(0, max_length - 200), -1):
            if remaining[i] in '.!?\n':
                last_sentence_end = i + 1
                break
        
        # Если не нашли, разбиваем по пробелам
        if last_sentence_end == -1:
            last_space = remaining.rfind(' ', 0, max_length)
            if last_space > max_length * 0.7:
                last_sentence_end = last_space
            else:
                last_sentence_end = max_length
        
        messages.append(remaining[:last_sentence_end].strip())
        remaining = remaining[last_sentence_end:].strip()
    
    if remaining:
        messages.append(remaining)
    
    return messages

async def send_approval_notification(bot: Bot, admin_chat_ids: list, restaurant_name: str):
    """Отправка уведомления админам о новой заявке на согласование"""
    from utils.keyboards import get_show_approvals_keyboard
    
    notification_text = (
        f"🔔 Новая заявка на согласование!\n\n"
        f"🏪 Ресторан: {restaurant_name}\n"
        f"📋 Поступила новая заявка на согласование изменений."
    )
    
    markup = get_show_approvals_keyboard()
    
    for admin_id in admin_chat_ids:
        try:
            await bot.send_message(admin_id, notification_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
