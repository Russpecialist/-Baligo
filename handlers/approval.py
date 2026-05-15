"""Обработчики для согласования изменений ресторанов"""
import os
import shutil
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from database.queries import (
    get_approval_request, approve_request, reject_request,
    get_user_role_by_chat_id, get_restaurant_by_id,
    get_promotion_event_approval, approve_promotion_event, reject_promotion_event
)
from utils.helpers import log_error, format_approval_message, format_newsletter_proposal, format_promotion_event_newsletter_proposal, split_text_for_caption, split_text_into_messages
from utils.keyboards import get_approval_keyboard, get_approval_newsletter_keyboard, get_newsletter_confirm_keyboard, get_promotion_event_approval_keyboard
from config import MENU_PATH, PENDING_MENU_PATH
from utils.pdf_converter import clear_cache, pdf_to_images
from states.bot_states import BotStates
from database.queries import get_all_chat_id
from aiogram.types import Message
import asyncio
import logging

logger = logging.getLogger(__name__)

# Обработчики как отдельные функции
async def handle_approve_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения запроса"""
    try:
        approval_id = int(callback.data.split("_")[1])
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        approval = await get_approval_request(approval_id)
        if not approval:
            await callback.answer("Запрос не найден.", show_alert=True)
            return
        
        # Если это меню или банкет, обрабатываем файлы
        if approval.get('field_name') == 'menu':
            temp_file_path = approval.get('new_value')  # В new_value хранится путь к временному файлу
            restaurant_id = approval.get('restaurant_id')
            restaurant = await get_restaurant_by_id(restaurant_id)
            
            if restaurant and temp_file_path and os.path.exists(temp_file_path):
                restaurant_name = restaurant.get('restaurant_name', '')
                menu_folder = os.path.join(MENU_PATH, restaurant_name)
                os.makedirs(menu_folder, exist_ok=True)
                
                # Определяем путь к старому файлу
                old_value = approval.get('old_value', '')
                old_file_path = None
                if old_value and old_value != 'Нет файла' and not old_value.startswith('/'):
                    # Если old_value - это имя файла, а не путь
                    old_file_path = os.path.join(menu_folder, old_value)
                
                # Удаляем старый файл и его кэш (если есть)
                if old_file_path and os.path.exists(old_file_path):
                    clear_cache(old_file_path)
                    os.remove(old_file_path)
        
        elif approval.get('field_name') == 'banquet':
            temp_file_path = approval.get('new_value')  # В new_value хранится путь к временному файлу
            restaurant_id = approval.get('restaurant_id')
            restaurant = await get_restaurant_by_id(restaurant_id)
            
            if restaurant and temp_file_path and os.path.exists(temp_file_path):
                restaurant_name = restaurant.get('restaurant_name', '')
                banquet_folder = os.path.join(MENU_PATH, restaurant_name, "Банкет")
                os.makedirs(banquet_folder, exist_ok=True)
                
                # Определяем путь к старому файлу
                old_value = approval.get('old_value', '')
                old_file_path = None
                if old_value and old_value != 'Нет файла' and not old_value.startswith('/'):
                    # Если old_value - это имя файла, а не путь
                    old_file_path = os.path.join(banquet_folder, old_value)
                
                # Удаляем старый файл и его кэш (если есть)
                if old_file_path and os.path.exists(old_file_path):
                    clear_cache(old_file_path)
                    os.remove(old_file_path)
                
                # Перемещаем новый файл из временной папки в папку банкетов
                file_name = os.path.basename(temp_file_path)
                final_path = os.path.join(banquet_folder, file_name)
                
                try:
                    shutil.move(temp_file_path, final_path)
                    
                    # Создаем кэш для нового файла
                    try:
                        await pdf_to_images(final_path)
                    except Exception as e:
                        logger.error(f"Ошибка создания кэша для банкетного файла {final_path}: {e}")
                    
                    # Обновляем new_value в БД на имя файла
                    from database.queries import db_manager
                    update_query = '''
                        UPDATE restaurant_approvals 
                        SET new_value = $1 
                        WHERE id = $2;
                    '''
                    await db_manager.execute_query(update_query, file_name, approval_id)
                    
                    logger.info(f"Банкет одобрен и применен: {final_path}")
                except Exception as e:
                    logger.error(f"Ошибка перемещения банкетного файла: {e}")
                    await callback.answer("Ошибка при применении изменений.", show_alert=True)
                    return
        
        success = await approve_request(approval_id, admin_chat_id)
        
        if success:
            requested_by = approval.get('requested_by')
            restaurant = await get_restaurant_by_id(approval.get('restaurant_id'))
            restaurant_name = restaurant.get('restaurant_name', 'ресторан') if restaurant else 'ресторан'
            bot = callback.bot
            
            try:
                await bot.send_message(
                    requested_by,
                    f"✅ Ваш запрос на изменение информации о ресторане '{restaurant_name}' был подтвержден администратором.\n"
                    f"Изменения применены."
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления ресторану {requested_by}: {e}")
            
            await callback.answer("Запрос подтвержден и изменения применены.", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Подтверждено администратором",
                reply_markup=None
            )
            
            # Отправляем предложение о рассылке
            # state уже доступен в callback, используем его
            await send_newsletter_proposal(bot, admin_chat_id, approval, state)
        else:
            await callback.answer("Ошибка при подтверждении запроса.", show_alert=True)
    
    except Exception as e:
        await log_error(e, f"approve_callback_{callback.data}")
        await callback.answer("Произошла ошибка при обработке запроса.", show_alert=True)

async def handle_reject_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка отклонения запроса"""
    try:
        approval_id = int(callback.data.split("_")[1])
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        approval = await get_approval_request(approval_id)
        if not approval:
            await callback.answer("Запрос не найден.", show_alert=True)
            return
        
        # Если это меню, удаляем временный файл
        if approval.get('field_name') == 'menu':
            temp_file_path = approval.get('new_value')  # В new_value хранится путь к временному файлу
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Временный файл меню удален: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления временного файла: {e}")
        
        elif approval.get('field_name') == 'banquet':
            temp_file_path = approval.get('new_value')  # В new_value хранится путь к временному файлу
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Временный банкетный файл удален: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления временного банкетного файла: {e}")
        
        success = await reject_request(approval_id, admin_chat_id)
        
        if success:
            requested_by = approval.get('requested_by')
            restaurant = await get_restaurant_by_id(approval.get('restaurant_id'))
            restaurant_name = restaurant.get('restaurant_name', 'ресторан') if restaurant else 'ресторан'
            bot = callback.bot
            
            try:
                await bot.send_message(
                    requested_by,
                    f"❌ Ваш запрос на изменение информации о ресторане '{restaurant_name}' был отклонен администратором."
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления ресторану {requested_by}: {e}")
            
            await callback.answer("Запрос отклонен.", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Отклонено администратором",
                reply_markup=None
            )
        else:
            await callback.answer("Ошибка при отклонении запроса.", show_alert=True)
    
    except Exception as e:
        await log_error(e, f"reject_callback_{callback.data}")
        await callback.answer("Произошла ошибка при обработке запроса.", show_alert=True)

async def handle_view_changes_callback(callback: CallbackQuery, state: FSMContext):
    """Просмотр деталей изменений"""
    try:
        approval_id = int(callback.data.split("_")[1])
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        approval = await get_approval_request(approval_id)
        if approval:
            msg_text = format_approval_message(approval)
            markup = get_approval_keyboard(approval_id)
            await callback.message.edit_text(msg_text, reply_markup=markup)
            await callback.answer()
        else:
            await callback.answer("Запрос не найден.", show_alert=True)
    
    except Exception as e:
        await log_error(e, f"view_callback_{callback.data}")
        await callback.answer("Произошла ошибка при просмотре запроса.", show_alert=True)

async def send_newsletter_proposal(bot, admin_chat_id: int, approval: dict, state: FSMContext):
    """Отправка предложения о рассылке после согласования"""
    newsletter_text = format_newsletter_proposal(approval)
    markup = get_approval_newsletter_keyboard()
    
    # Сохраняем данные для рассылки в state
    await state.update_data(
        approval_id=approval.get('id'),
        restaurant_id=approval.get('restaurant_id'),
        field_name=approval.get('field_name'),
        restaurant_name=approval.get('restaurant_name', 'ресторан'),
        default_newsletter_text=newsletter_text
    )
    
    await bot.send_message(
        admin_chat_id,
        f"{newsletter_text}\n\nЧто хотите сделать?",
        reply_markup=markup
    )
    await state.set_state(BotStates.waiting_approval_newsletter)

async def send_promotion_event_newsletter_proposal(bot, admin_chat_id: int, approval: dict, state: FSMContext):
    """Отправка предложения о рассылке после согласования акции/события"""
    newsletter_text = format_promotion_event_newsletter_proposal(approval)
    markup = get_approval_newsletter_keyboard()
    
    # Сохраняем данные для рассылки в state
    await state.update_data(
        approval_id=approval.get('id'),
        restaurant_id=approval.get('restaurant_id'),
        type=approval.get('type'),  # 'promotion' или 'event'
        item_id=approval.get('item_id'),  # ID акции/события
        title=approval.get('title'),
        description=approval.get('description'),
        photo_file_id=approval.get('photo_file_id'),
        restaurant_name=approval.get('restaurant_name', 'ресторан'),
        default_newsletter_text=newsletter_text,
        is_promotion_event=True  # Флаг, что это рассылка для акций/событий
    )
    
    await bot.send_message(
        admin_chat_id,
        f"{newsletter_text}\n\nЧто хотите сделать?",
        reply_markup=markup
    )
    await state.set_state(BotStates.waiting_approval_newsletter)

async def handle_approval_newsletter(message: Message, state: FSMContext):
    """Обработка выбора действия с рассылкой"""
    data = await state.get_data()
    default_text = data.get('default_newsletter_text', '')
    
    if message.text == "❌ Не отправлять рассылку":
        await message.answer("Рассылка отменена.")
        await state.clear()
        from handlers.common import main_menu
        await main_menu(message, state)
        return
    
    elif message.text == "✏️ Изменить рассылку":
        await message.answer(
            "Введите новый текст для рассылки:",
            reply_markup=get_newsletter_confirm_keyboard()
        )
        await state.set_state(BotStates.waiting_approval_newsletter_edit)
        return
    
    elif message.text == "✉ Отправить рассылку":
        # Отправляем рассылку с текстом по умолчанию
        await send_newsletter_to_all(message, state, default_text)
        return
    
    else:
        # Если админ пишет что-то кроме кнопок - рассылка отменяется
        await message.answer("Рассылка отменена (неизвестная команда).")
        await state.clear()
        from handlers.common import main_menu
        await main_menu(message, state)
        return

async def handle_approval_newsletter_edit(message: Message, state: FSMContext):
    """Обработка редактирования текста рассылки"""
    if message.text == "⬅️ Вернуться назад":
        data = await state.get_data()
        default_text = data.get('default_newsletter_text', '')
        await message.answer(
            f"{default_text}\n\nЧто хотите сделать?",
            reply_markup=get_approval_newsletter_keyboard()
        )
        await state.set_state(BotStates.waiting_approval_newsletter)
        return
    
    # Сохраняем отредактированный текст
    await state.update_data(custom_newsletter_text=message.text)
    
    await message.answer(
        f"Текст рассылки:\n\n{message.text}\n\nПодтвердите отправку:",
        reply_markup=get_newsletter_confirm_keyboard()
    )
    await state.set_state(BotStates.waiting_approval_newsletter_confirm)

async def handle_approval_newsletter_confirm(message: Message, state: FSMContext):
    """Обработка подтверждения отправки рассылки"""
    if message.text == "⬅️ Вернуться назад":
        data = await state.get_data()
        default_text = data.get('default_newsletter_text', '')
        await message.answer(
            f"{default_text}\n\nЧто хотите сделать?",
            reply_markup=get_approval_newsletter_keyboard()
        )
        await state.set_state(BotStates.waiting_approval_newsletter)
        return
    
    elif message.text == "✅ Отправить рассылку":
        data = await state.get_data()
        # Используем кастомный текст, если есть, иначе дефолтный
        newsletter_text = data.get('custom_newsletter_text') or data.get('default_newsletter_text', '')
        await send_newsletter_to_all(message, state, newsletter_text)
        return
    
    else:
        # Если админ пишет что-то кроме кнопок - рассылка отменяется
        await message.answer("Рассылка отменена (неизвестная команда).")
        await state.clear()
        from handlers.common import main_menu
        await main_menu(message, state)
        return

async def send_newsletter_to_all(message: Message, state: FSMContext, newsletter_text: str):
    """Отправка рассылки всем пользователям"""
    try:
        data = await state.get_data()
        is_promotion_event = data.get('is_promotion_event', False)
        
        # Если это рассылка для акций/событий, используем специальный формат
        if is_promotion_event:
            await send_promotion_event_newsletter(message, state, newsletter_text)
            return
        
        # Проверяем, используется ли стандартный текст (не кастомный)
        custom_text = data.get('custom_newsletter_text')
        restaurant_id = data.get('restaurant_id')
        
        # Если используется стандартный текст (не кастомный), добавляем информацию о бронировании
        final_newsletter_text = newsletter_text
        if not custom_text and restaurant_id:
            try:
                restaurant = await get_restaurant_by_id(restaurant_id)
                if restaurant:
                    reservation_info = restaurant.get('reservation', '')
                    if reservation_info:
                        final_newsletter_text = f"{newsletter_text}\n\nДля бронирования:\n📋 {reservation_info}"
            except Exception as e:
                logger.error(f"Ошибка получения информации о бронировании для ресторана {restaurant_id}: {e}")
        
        # Получаем список всех активных пользователей
        chat_ids = await get_all_chat_id()
        
        if not chat_ids:
            await message.answer("Нет активных пользователей для рассылки.")
            await state.clear()
            return
        
        bot = message.bot
        success_count = 0
        error_count = 0
        
        await message.answer(f"Начинаю рассылку для {len(chat_ids)} пользователей...")
        
        # Разбиваем текст на части, если он слишком длинный
        from utils.helpers import split_text_into_messages
        newsletter_parts = split_text_into_messages(final_newsletter_text, max_length=4096)
        
        for chat_id_tuple in chat_ids:
            chat_id = chat_id_tuple[0]
            try:
                # Отправляем все части сообщения
                for i, part in enumerate(newsletter_parts):
                    await bot.send_message(chat_id, part)
                    # Небольшая задержка между частями
                    if i < len(newsletter_parts) - 1:
                        await asyncio.sleep(0.1)
                success_count += 1
                # Небольшая задержка, чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.05)
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка отправки рассылки пользователю {chat_id}: {e}")
        
        await message.answer(
            f"✅ Рассылка завершена!\n"
            f"Успешно отправлено: {success_count}\n"
            f"Ошибок: {error_count}"
        )
        
        # Возвращаемся в админское меню
        from handlers.common import main_menu
        from database.queries import get_user_role_by_chat_id
        from utils.keyboards import get_main_menu_keyboard
        from states.bot_states import BotStates
        
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Очищаем state и показываем админское меню
            await state.clear()
            markup = get_main_menu_keyboard('admin')
            await message.answer('Что необходимо сделать?', reply_markup=markup)
            await state.set_state(BotStates.waiting_admin_action)
        else:
            await state.clear()
        
    except Exception as e:
        await log_error(e, "newsletter_send")
        await message.answer("❌ Ошибка при отправке рассылки.")
        
        # Возвращаемся в админское меню даже при ошибке
        from database.queries import get_user_role_by_chat_id
        from utils.keyboards import get_main_menu_keyboard
        from states.bot_states import BotStates
        
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Очищаем state и показываем админское меню
            await state.clear()
            markup = get_main_menu_keyboard('admin')
            await message.answer('Что необходимо сделать?', reply_markup=markup)
            await state.set_state(BotStates.waiting_admin_action)
        else:
            await state.clear()

async def send_promotion_event_newsletter(message: Message, state: FSMContext, header_text: str):
    """Отправка рассылки для акций/событий в специальном формате"""
    try:
        data = await state.get_data()
        title = data.get('title', '')
        description = data.get('description', '')
        photo_file_id = data.get('photo_file_id')
        
        # Получаем список всех активных пользователей
        chat_ids = await get_all_chat_id()
        
        if not chat_ids:
            await message.answer("Нет активных пользователей для рассылки.")
            await state.clear()
            return
        
        bot = message.bot
        success_count = 0
        error_count = 0
        
        await message.answer(f"Начинаю рассылку для {len(chat_ids)} пользователей...")
        
        # Формируем текст события/акции
        event_text = f"{title}\n\n{description}" if description else title
        
        # Разбиваем текст на части, если он слишком длинный
        event_parts = split_text_into_messages(event_text, max_length=4096)
        
        for chat_id_tuple in chat_ids:
            chat_id = chat_id_tuple[0]
            try:
                # 1. Отправляем заголовок: "В ресторане {название} новое событие:"
                await bot.send_message(chat_id, header_text)
                await asyncio.sleep(0.05)
                
                # 2. Отправляем событие/акцию с фото (если есть) или без
                if photo_file_id:
                    # Если есть фото, отправляем первое сообщение с фото и подписью
                    if event_parts:
                        # Разбиваем первый текст на подпись и остаток
                        caption_text, remaining_text = split_text_for_caption(event_parts[0], max_length=1024)
                        
                        try:
                            await bot.send_photo(chat_id, photo_file_id, caption=caption_text)
                        except Exception as e:
                            logger.error(f"Ошибка отправки фото пользователю {chat_id}: {e}")
                            # Если не удалось отправить с фото, отправляем как текст
                            await bot.send_message(chat_id, event_parts[0])
                        
                        # Отправляем остаток текста отдельными сообщениями
                        if remaining_text:
                            remaining_parts = split_text_into_messages(remaining_text, max_length=4096)
                            for part in remaining_parts:
                                await bot.send_message(chat_id, part)
                                await asyncio.sleep(0.1)
                        
                        # Отправляем остальные части текста
                        for part in event_parts[1:]:
                            await bot.send_message(chat_id, part)
                            await asyncio.sleep(0.1)
                    else:
                        # Если текста нет, отправляем только фото
                        await bot.send_photo(chat_id, photo_file_id)
                else:
                    # Если нет фото, отправляем только текст
                    for i, part in enumerate(event_parts):
                        await bot.send_message(chat_id, part)
                        if i < len(event_parts) - 1:
                            await asyncio.sleep(0.1)
                
                success_count += 1
                # Небольшая задержка, чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.05)
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка отправки рассылки пользователю {chat_id}: {e}")
        
        await message.answer(
            f"✅ Рассылка завершена!\n"
            f"Успешно отправлено: {success_count}\n"
            f"Ошибок: {error_count}"
        )
        
        # Возвращаемся в админское меню
        from handlers.common import main_menu
        from database.queries import get_user_role_by_chat_id
        from utils.keyboards import get_main_menu_keyboard
        from states.bot_states import BotStates
        
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Очищаем state и показываем админское меню
            await state.clear()
            markup = get_main_menu_keyboard('admin')
            await message.answer('Что необходимо сделать?', reply_markup=markup)
            await state.set_state(BotStates.waiting_admin_action)
        else:
            await state.clear()
        
    except Exception as e:
        await log_error(e, "promotion_event_newsletter_send")
        await message.answer("❌ Ошибка при отправке рассылки.")
        
        # Возвращаемся в админское меню даже при ошибке
        from database.queries import get_user_role_by_chat_id
        from utils.keyboards import get_main_menu_keyboard
        from states.bot_states import BotStates
        
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Очищаем state и показываем админское меню
            await state.clear()
            markup = get_main_menu_keyboard('admin')
            await message.answer('Что необходимо сделать?', reply_markup=markup)
            await state.set_state(BotStates.waiting_admin_action)
        else:
            await state.clear()

async def handle_show_approvals_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Показать заявки'"""
    try:
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        # Подтверждаем нажатие кнопки
        await callback.answer("Загружаю заявки...")
        
        # Импортируем функцию показа заявок
        from handlers.admin import show_pending_approvals
        
        # Используем callback.message напрямую
        # В aiogram 3.x callback.message содержит все необходимые поля
        await show_pending_approvals(callback.message, state)
        
    except Exception as e:
        await log_error(e, f"show_approvals_callback")
        await callback.answer("Произошла ошибка при загрузке заявок.", show_alert=True)

async def handle_promotion_event_approve_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения запроса на акцию/событие"""
    try:
        approval_id = int(callback.data.split("_")[2])
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        approval = await get_promotion_event_approval(approval_id)
        if not approval:
            await callback.answer("Запрос не найден.", show_alert=True)
            return
        
        success = await approve_promotion_event(approval_id, admin_chat_id)
        if success:
            requested_by = approval.get('requested_by')
            restaurant = await get_restaurant_by_id(approval.get('restaurant_id'))
            restaurant_name = restaurant.get('restaurant_name', 'ресторан') if restaurant else 'ресторан'
            bot = callback.bot
            
            try:
                await bot.send_message(
                    requested_by,
                    f"✅ Ваш запрос на изменение акции/события в ресторане '{restaurant_name}' был подтвержден администратором.\n"
                    f"Изменения применены."
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления ресторану {requested_by}: {e}")
            
            await callback.answer("✅ Запрос одобрен")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("✅ Запрос на изменение акции/события одобрен и применен.")
            
            # Отправляем предложение о рассылке
            await send_promotion_event_newsletter_proposal(bot, admin_chat_id, approval, state)
        else:
            await callback.answer("❌ Ошибка при одобрении запроса", show_alert=True)
    except Exception as e:
        await log_error(e, "promotion_event_approve")
        await callback.answer("Произошла ошибка", show_alert=True)

async def handle_promotion_event_reject_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка отклонения запроса на акцию/событие"""
    try:
        approval_id = int(callback.data.split("_")[2])
        admin_chat_id = callback.from_user.id
        
        role, status = await get_user_role_by_chat_id(admin_chat_id)
        if role != 'admin' or status != 'active':
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return
        
        success = await reject_promotion_event(approval_id, admin_chat_id)
        if success:
            await callback.answer("❌ Запрос отклонен")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("❌ Запрос на изменение акции/события отклонен.")
        else:
            await callback.answer("❌ Ошибка при отклонении запроса", show_alert=True)
    except Exception as e:
        await log_error(e, "promotion_event_reject")
        await callback.answer("Произошла ошибка", show_alert=True)

def register_approval_handlers(dp, bot):
    """Регистрация обработчиков для согласований"""
    from aiogram import F
    from aiogram.filters import StateFilter
    
    dp.callback_query.register(handle_approve_callback, lambda c: c.data.startswith("approve_") and not c.data.startswith("pe_approve_"))
    dp.callback_query.register(handle_reject_callback, lambda c: c.data.startswith("reject_") and not c.data.startswith("pe_reject_"))
    dp.callback_query.register(handle_view_changes_callback, lambda c: c.data.startswith("view_"))
    dp.callback_query.register(handle_show_approvals_callback, lambda c: c.data == "show_approvals")
    
    # Обработчики для акций и событий
    dp.callback_query.register(handle_promotion_event_approve_callback, lambda c: c.data.startswith("pe_approve_"))
    dp.callback_query.register(handle_promotion_event_reject_callback, lambda c: c.data.startswith("pe_reject_"))
    
    # Регистрация обработчиков для рассылки
    dp.message.register(handle_approval_newsletter, StateFilter(BotStates.waiting_approval_newsletter))
    dp.message.register(handle_approval_newsletter_edit, StateFilter(BotStates.waiting_approval_newsletter_edit))
    dp.message.register(handle_approval_newsletter_confirm, StateFilter(BotStates.waiting_approval_newsletter_confirm))
    
    logger.info("Approval handlers зарегистрированы")
