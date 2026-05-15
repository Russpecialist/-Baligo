"""Обработчики для администраторов"""
import asyncio
import os
import re
from aiogram import F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from config import MENU_PATH
from utils.pdf_converter import pdf_to_images, clear_cache
from database.queries import (
    change_role_sql, change_status_sql, get_all_chat_id, get_regions,
    get_pending_approvals, create_restaurant, get_all_restaurants,
    update_restaurant, add_user_restaurant, get_chat_id, delete_restaurant,
    db_manager, CATEGORIES, CATEGORY_LABEL_TO_DB
)
from utils.telegram_helpers import get_chat_id_from_username
from utils.keyboards import (
    get_cancel_keyboard, get_restaurant_confirm_keyboard, get_restaurants_list_keyboard,
    get_regions_keyboard, get_restaurant_edit_keyboard, get_delete_confirm_keyboard,
    get_categories_keyboard
)
from utils.helpers import log_error, split_text_for_caption, split_text_into_messages
from handlers.user import show_regions_or_restaurants
from handlers.common import main_menu
from states.bot_states import BotStates
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
import logging

logger = logging.getLogger(__name__)

# Вспомогательные функции


async def show_pending_approvals(message: Message, state: FSMContext):
    """Показать список ожидающих согласования запросов"""
    from database.queries import get_pending_promotion_event_approvals

    restaurant_approvals = await get_pending_approvals()
    promotion_event_approvals = await get_pending_promotion_event_approvals()

    if not restaurant_approvals and not promotion_event_approvals:
        await message.answer("Нет запросов на согласование.")
        return

    from utils.helpers import format_approval_message, send_menu_approval_message, format_promotion_event_approval_message
    from utils.keyboards import get_approval_keyboard, get_promotion_event_approval_keyboard
    from config import MENU_PATH, PENDING_MENU_PATH
    import os

    bot = message.bot

    for approval in restaurant_approvals:
        if approval.get('field_name') == 'menu':
            temp_file_path = approval.get('new_value')
            restaurant_id = approval.get('restaurant_id')
            old_value = approval.get('old_value', '')
            old_file_path = None
            if old_value and old_value != 'Нет файла' and not old_value.startswith('/'):
                from database.queries import get_restaurant_by_id
                restaurant = await get_restaurant_by_id(restaurant_id)
                if restaurant:
                    restaurant_name = restaurant.get('restaurant_name', '')
                    menu_folder = os.path.join(MENU_PATH, restaurant_name)
                    old_file_path = os.path.join(menu_folder, old_value)
                    if not os.path.exists(old_file_path):
                        old_file_path = None
            await send_menu_approval_message(
                bot, message.chat.id, approval, old_file_path, temp_file_path
            )
        else:
            msg_text = format_approval_message(approval)
            markup = get_approval_keyboard(approval['id'])
            await message.answer(msg_text, reply_markup=markup)

    for approval in promotion_event_approvals:
        msg_text = format_promotion_event_approval_message(approval)
        markup = get_promotion_event_approval_keyboard(approval['id'])
        if approval.get('photo_file_id'):
            await bot.send_photo(
                message.chat.id,
                approval['photo_file_id'],
                caption=msg_text,
                reply_markup=markup
            )
        else:
            await message.answer(msg_text, reply_markup=markup)


async def handle_admin_action(message: Message, state: FSMContext):
    """Обработка действий администратора"""
    current_state = await state.get_state()
    logger.debug(
        f"handle_admin_action: получено сообщение '{message.text}' от пользователя {message.from_user.id}, состояние: {current_state}")

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='🏠 Вернуться в главное меню')]],
        resize_keyboard=True
    )

    if message.text == "⛔ Забанить пользователя":
        await message.answer('Введите username пользователя (@username):', reply_markup=markup)
        await state.update_data(role_action='banned')
        await state.set_state(BotStates.waiting_username)

    elif message.text == "✅ Разбанить пользователя":
        await message.answer('Введите username пользователя (@username):', reply_markup=markup)
        await state.update_data(role_action='user')
        await state.set_state(BotStates.waiting_username)

    elif message.text == "⭐ Добавить админа":
        await message.answer('Введите username пользователя (@username):', reply_markup=markup)
        await state.update_data(role_action='admin')
        await state.set_state(BotStates.waiting_username)

    elif message.text == "❌ Удалить админа":
        await message.answer('Введите username пользователя (@username):', reply_markup=markup)
        await state.update_data(role_action='user')
        await state.set_state(BotStates.waiting_username)

    elif message.text == "🚶 Вернуться в меню пользователя":
        await show_regions_or_restaurants(message, state, is_admin=True)

    elif message.text == "✉ Отправить рассылку":
        await message.answer('✏ Введите текст рассылки:', reply_markup=markup)
        await state.set_state(BotStates.waiting_newsletter)

    elif message.text == "📋 Запросы на согласование":
        await show_pending_approvals(message, state)

    elif message.text == "🏢 Личный кабинет ресторана":
        from utils.keyboards import get_restaurant_cabinet_keyboard
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        return

    elif message.text == "➕ Добавить ресторан":
        await message.answer(
            'Введите название ресторана:',
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(BotStates.waiting_restaurant_name)

    elif message.text == "✏️ Изменить ресторан":
        restaurants = await get_all_restaurants()
        if not restaurants:
            await message.answer("Нет ресторанов для редактирования.")
            await main_menu(message, state)
            return
        restaurant_names = [r['restaurant_name'] for r in restaurants]
        markup = get_restaurants_list_keyboard(restaurant_names)
        await message.answer('Выберите ресторан для редактирования:', reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_edit_selection)

    else:
        await message.answer("Неизвестная команда администратора. Выберите из предложенных вариантов.")
        await main_menu(message, state)


async def handle_username_input(message: Message, state: FSMContext):
    """Обработка ввода username для изменения роли"""
    if message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
        return

    username = message.text.strip()
    data = await state.get_data()
    role = data.get('role_action')

    db_username = username if username.startswith('@') else f'@{username}'
    chat_id = await get_chat_id(db_username)

    if not chat_id:
        bot = message.bot
        chat_id = await get_chat_id_from_username(bot, username)
        if not chat_id:
            await message.answer(
                f'❌ Не удалось найти пользователя {username}.\n\n'
                'Возможные причины:\n'
                '• Username указан неверно\n'
                '• Пользователь не начинал диалог с ботом\n'
                '• Профиль пользователя скрыт\n\n'
                'Попробуйте ввести username еще раз:',
                reply_markup=get_cancel_keyboard()
            )
            return

    try:
        from database.queries import db_manager
        update_query = 'UPDATE users SET role = $1 WHERE chat_id = $2;'
        await db_manager.execute_query(update_query, role, chat_id)
        logger.info(
            f"Роль пользователя {username} (chat_id={chat_id}) изменена на {role}")
        await message.answer(f'✅ Роль пользователя {username} изменена на {role}')
    except Exception as e:
        logger.error(f"Ошибка изменения роли пользователя {username}: {e}")
        await message.answer(f'❌ Ошибка при изменении роли пользователя {username}')

    await main_menu(message, state)


async def handle_newsletter_input(message: Message, state: FSMContext):
    """Обработка ввода текста рассылки"""
    if message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
        return

    buttons = [[KeyboardButton(text='Да'), KeyboardButton(text='Нет')]]
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer('Подтвердить отправку?', reply_markup=markup)
    await state.update_data(newsletter_message=message)
    await state.set_state(BotStates.waiting_newsletter_confirm)


async def handle_newsletter_confirm(message: Message, state: FSMContext):
    """Подтверждение и отправка рассылки"""
    if message.text == 'Да':
        data = await state.get_data()
        newsletter_message = data.get('newsletter_message')
        bot = message.bot

        chat_id_list = await get_all_chat_id()
        g_count = 0
        b_count = 0
        inactive_chat_id = []

        for chat_id in chat_id_list:
            await asyncio.sleep(0.15)
            try:
                if newsletter_message.content_type == 'text':
                    await bot.send_message(chat_id[0], newsletter_message.text)
                elif newsletter_message.content_type == 'photo':
                    caption = newsletter_message.caption or ""
                    caption_text, remaining_text = split_text_for_caption(
                        caption, max_length=1024)
                    await bot.send_photo(chat_id[0], photo=newsletter_message.photo[-1].file_id, caption=caption_text if caption_text else None)
                    if remaining_text:
                        for part in split_text_into_messages(remaining_text, max_length=4096):
                            await bot.send_message(chat_id[0], part)
                            await asyncio.sleep(0.1)
                elif newsletter_message.content_type == 'video':
                    caption = newsletter_message.caption or ""
                    caption_text, remaining_text = split_text_for_caption(
                        caption, max_length=1024)
                    await bot.send_video(chat_id[0], video=newsletter_message.video.file_id, caption=caption_text if caption_text else None)
                    if remaining_text:
                        for part in split_text_into_messages(remaining_text, max_length=4096):
                            await bot.send_message(chat_id[0], part)
                            await asyncio.sleep(0.1)
                else:
                    await message.answer('⛔ Отправка разрешена только в виде текста, фото, видео')
                    break
                g_count += 1
            except TelegramForbiddenError:
                await message.answer(f'❌ Не удалось отправить рассылку пользователю: tg://user?id={chat_id[0]}')
                b_count += 1
                inactive_chat_id.append(chat_id[0])
            except TelegramRetryAfter as e:
                await message.answer(f'Превышен лимит запросов. Ждем {e.retry_after} секунд')
                await asyncio.sleep(e.retry_after)
            except TelegramBadRequest as e:
                if 'message caption is too long' in str(e):
                    await message.answer('Слишком длинное сообщение')
                    break
                else:
                    await log_error(e, "newsletter")
                    break
            except Exception as e:
                await log_error(e, "newsletter")
                break

        for chat_id in inactive_chat_id:
            await change_status_sql('inactive', chat_id)

        await message.answer(f'✅ Успешно отправлено: {g_count} \n❌ Не удалось отправить: {b_count}')
        await main_menu(message, state)
    else:
        await main_menu(message, state)


async def handle_restaurant_name_input(message: Message, state: FSMContext):
    """Обработка ввода названия ресторана"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    await state.update_data(restaurant_name=message.text)
    await message.answer('Введите адрес ресторана:', reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_restaurant_address)


async def handle_restaurant_address_input(message: Message, state: FSMContext):
    """Обработка ввода адреса ресторана"""
    if message.text == "❌ Отменить":
        await message.answer('Введите название ресторана:', reply_markup=get_cancel_keyboard())
        await state.set_state(BotStates.waiting_restaurant_name)
        return
    await state.update_data(address_nm=message.text)
    await message.answer('Введите информацию о бронировании:', reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_restaurant_reservation)


async def handle_restaurant_reservation_input(message: Message, state: FSMContext):
    """Обработка ввода информации о бронировании"""
    if message.text == "❌ Отменить":
        await message.answer('Введите адрес ресторана:', reply_markup=get_cancel_keyboard())
        await state.set_state(BotStates.waiting_restaurant_address)
        return
    await state.update_data(reservation=message.text)
    await message.answer('Введите информацию о доставке:', reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_restaurant_delivery)


async def handle_restaurant_delivery_input(message: Message, state: FSMContext):
    """Обработка ввода информации о доставке"""
    if message.text == "❌ Отменить":
        await message.answer('Введите информацию о бронировании:', reply_markup=get_cancel_keyboard())
        await state.set_state(BotStates.waiting_restaurant_reservation)
        return
    await state.update_data(delivery=message.text)
    await message.answer('Введите район (Canggu, Ubud, Seminyak или Uluwatu):', reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_restaurant_region)


async def handle_restaurant_region_input(message: Message, state: FSMContext):
    """Обработка ввода региона"""
    if message.text == "❌ Отменить":
        await message.answer('Введите информацию о доставке:', reply_markup=get_cancel_keyboard())
        await state.set_state(BotStates.waiting_restaurant_delivery)
        return
    await state.update_data(region_nm=message.text)
    await message.answer(
        'Выберите категорию партнёра:',
        reply_markup=get_categories_keyboard(CATEGORIES)
    )
    await state.set_state(BotStates.waiting_restaurant_category)


async def handle_restaurant_category_input(message: Message, state: FSMContext):
    """Обработка выбора категории партнёра при создании"""
    if message.text in ("❌ Отменить", "⬅️ Назад к районам"):
        await message.answer('Введите район:', reply_markup=get_cancel_keyboard())
        await state.set_state(BotStates.waiting_restaurant_region)
        return

    if message.text not in CATEGORY_LABEL_TO_DB:
        await message.answer(
            'Пожалуйста, выберите категорию из списка:',
            reply_markup=get_categories_keyboard(CATEGORIES)
        )
        return

    category_db = CATEGORY_LABEL_TO_DB[message.text]
    await state.update_data(category=category_db)
    await message.answer(
        'Введите Telegram username администратора ресторана (@username):',
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BotStates.waiting_restaurant_username)


async def handle_restaurant_username_input(message: Message, state: FSMContext):
    """Обработка ввода username администратора"""
    if message.text == "❌ Отменить":
        await message.answer(
            'Выберите категорию партнёра:',
            reply_markup=get_categories_keyboard(CATEGORIES)
        )
        await state.set_state(BotStates.waiting_restaurant_category)
        return

    username = message.text.strip()
    bot = message.bot

    db_username = username if username.startswith('@') else f'@{username}'
    chat_id = await get_chat_id(db_username)

    if chat_id:
        logger.info(f"Пользователь {username} найден в БД: chat_id={chat_id}")
    else:
        chat_id = await get_chat_id_from_username(bot, username)
        if chat_id:
            logger.info(
                f"Пользователь {username} найден через Telegram API: chat_id={chat_id}")

    if not chat_id:
        await message.answer(
            f'❌ Не удалось найти пользователя {username}.\n\n'
            'Возможные причины:\n'
            '• Username указан неверно\n'
            '• Пользователь не начинал диалог с ботом\n'
            '• Профиль пользователя скрыт\n\n'
            'Попробуйте ввести username еще раз:',
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.update_data(admin_username=username, admin_chat_id=chat_id)
    data = await state.get_data()
    confirm_text = (
        '📋 Проверьте введенные данные:\n\n'
        f'🏪 Название: {data.get("restaurant_name")}\n'
        f'📍 Адрес: {data.get("address_nm")}\n'
        f'📞 Бронирование: {data.get("reservation")}\n'
        f'🚚 Доставка: {data.get("delivery")}\n'
        f'🌴 Район: {data.get("region_nm")}\n'
        f'🗂 Категория: {data.get("category", "не указана")}\n'
        f'👤 Администратор: @{username.lstrip("@")} (ID: {chat_id})\n\n'
        'Подтвердите создание партнёра:'
    )
    await message.answer(confirm_text, reply_markup=get_restaurant_confirm_keyboard())
    await state.set_state(BotStates.waiting_restaurant_confirm)


async def handle_restaurant_confirm(message: Message, state: FSMContext):
    """Подтверждение и создание ресторана"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return

    if message.text != "✅ Добавить":
        await message.answer('Используйте кнопки для подтверждения или отмены.', reply_markup=get_restaurant_confirm_keyboard())
        return

    data = await state.get_data()

    try:
        restaurant_id = await create_restaurant(
            restaurant_name=data.get('restaurant_name'),
            address_nm=data.get('address_nm'),
            reservation=data.get('reservation'),
            delivery=data.get('delivery'),
            region_nm=data.get('region_nm'),
            category=data.get('category')
        )

        if not restaurant_id:
            await message.answer('❌ Ошибка при создании ресторана. Попробуйте позже.')
            await main_menu(message, state)
            return

        admin_chat_id = data.get('admin_chat_id')
        if admin_chat_id:
            from database.queries import db_manager
            check_query = 'SELECT chat_id FROM users WHERE chat_id = $1;'
            user_exists = await db_manager.fetchrow_query(check_query, admin_chat_id)

            if not user_exists:
                username = data.get('admin_username', '').lstrip('@')
                insert_query = '''
                    INSERT INTO users (chat_id, username, role, status)
                    VALUES ($1, $2, 'restaurant', 'active')
                    ON CONFLICT (chat_id) DO NOTHING;
                '''
                db_username = f'@{username}' if username and not username.startswith(
                    '@') else username or None
                await db_manager.execute_query(insert_query, admin_chat_id, db_username)
            else:
                update_query = 'UPDATE users SET role = \'restaurant\' WHERE chat_id = $1;'
                await db_manager.execute_query(update_query, admin_chat_id)

            await add_user_restaurant(admin_chat_id, restaurant_id)

        await message.answer(
            f'✅ Партнёр "{data.get("restaurant_name")}" успешно создан!\n'
            f'ID: {restaurant_id}'
        )
        await main_menu(message, state)

    except Exception as e:
        await log_error(e, "restaurant_creation")
        await message.answer('❌ Ошибка при создании партнёра. Попробуйте позже.')
        await main_menu(message, state)


async def handle_restaurant_edit_selection(message: Message, state: FSMContext):
    """Обработка выбора ресторана для редактирования"""
    if message.text in ("❌ Отменить", "🏠 Вернуться в главное меню"):
        await main_menu(message, state)
        return

    restaurants = await get_all_restaurants()
    restaurant_dict = {r['restaurant_name']: r for r in restaurants}

    if message.text not in restaurant_dict:
        await message.answer('Ресторан не найден. Выберите из списка:', reply_markup=get_restaurants_list_keyboard([r['restaurant_name'] for r in restaurants]))
        return

    selected_restaurant = restaurant_dict[message.text]
    restaurant_id = selected_restaurant['restaurant_id']

    from database.queries import get_restaurant_by_id
    restaurant_data = await get_restaurant_by_id(restaurant_id)

    if not restaurant_data:
        await message.answer('❌ Ошибка при загрузке данных ресторана.')
        await main_menu(message, state)
        return

    await state.update_data(
        editing_restaurant_id=restaurant_id,
        editing_restaurant_name=restaurant_data.get('restaurant_name', ''),
        editing_address_nm=restaurant_data.get('address_nm', ''),
        editing_reservation=restaurant_data.get('reservation', ''),
        editing_delivery=restaurant_data.get('delivery', ''),
        editing_region_nm=restaurant_data.get('region_nm', '')
    )

    edit_text = (
        f'✏️ Редактирование: {restaurant_data.get("restaurant_name")}\n\n'
        'Отправьте сообщение в формате:\n'
        'Название: <новое название>\n'
        'Адрес: <новый адрес>\n'
        'Бронирование: <новая информация>\n'
        'Доставка: <новая информация>\n'
        'Регион: <новый регион>\n\n'
        'Текущие значения:\n'
        f'Название: {restaurant_data.get("restaurant_name", "не указано")}\n'
        f'Адрес: {restaurant_data.get("address_nm", "не указано")}\n'
        f'Бронирование: {restaurant_data.get("reservation", "не указано")}\n'
        f'Доставка: {restaurant_data.get("delivery", "не указано")}\n'
        f'Регион: {restaurant_data.get("region_nm", "не указано")}'
    )

    await message.answer(edit_text, reply_markup=get_restaurant_edit_keyboard())
    await state.set_state(BotStates.waiting_restaurant_edit_all)


async def handle_restaurant_edit_all(message: Message, state: FSMContext):
    """Обработка редактирования всех полей ресторана"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return

    if message.text == "📄 Изменить меню":
        data = await state.get_data()
        restaurant_id = data.get('editing_restaurant_id')
        if not restaurant_id:
            await message.answer('❌ Ошибка: ресторан не выбран.')
            await main_menu(message, state)
            return
        from database.queries import get_restaurant_by_id
        restaurant_data = await get_restaurant_by_id(restaurant_id)
        if restaurant_data:
            restaurant_name = restaurant_data.get('restaurant_name', '')
            menu_folder = os.path.join(MENU_PATH, restaurant_name)
            os.makedirs(menu_folder, exist_ok=True)
            await state.update_data(menu_folder=menu_folder, restaurant_name=restaurant_name, editing_restaurant_id=restaurant_id)
            from handlers.restaurant import show_menu_manager
            await show_menu_manager(message, state, menu_folder)
            return
        else:
            await message.answer('❌ Ошибка: ресторан не найден.')
            await main_menu(message, state)
            return

    if message.text == "🗑️ Удалить ресторан":
        data = await state.get_data()
        restaurant_id = data.get('editing_restaurant_id')
        restaurant_name = data.get('editing_restaurant_name', 'ресторан')
        if not restaurant_id:
            await message.answer('❌ Ошибка: ресторан не выбран.')
            await main_menu(message, state)
            return
        await message.answer(
            f'⚠️ Вы уверены, что хотите удалить "{restaurant_name}"?\n\nЭто действие нельзя отменить!',
            reply_markup=get_delete_confirm_keyboard()
        )
        await state.set_state(BotStates.waiting_restaurant_delete_confirm)
        return

    data = await state.get_data()
    restaurant_id = data.get('editing_restaurant_id')
    if not restaurant_id:
        await message.answer('❌ Ошибка: ресторан не выбран.')
        await main_menu(message, state)
        return

    updates = {}
    for line in message.text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if 'название' in key:
                updates['restaurant_name'] = value
            elif 'адрес' in key:
                updates['address_nm'] = value
            elif 'бронирование' in key:
                updates['reservation'] = value
            elif 'доставка' in key:
                updates['delivery'] = value
            elif 'регион' in key:
                updates['region_nm'] = value

    if not updates:
        await message.answer('❌ Не удалось распознать данные. Используйте формат:\nНазвание: <значение>', reply_markup=get_restaurant_edit_keyboard())
        return

    success = await update_restaurant(restaurant_id, **updates)
    if success:
        await message.answer(f'✅ Обновлено: {", ".join(updates.keys())}')
    else:
        await message.answer('❌ Ошибка при обновлении.')
    await main_menu(message, state)


async def handle_restaurant_delete_confirm(message: Message, state: FSMContext):
    """Подтверждение удаления ресторана"""
    if message.text == "❌ Отменить":
        data = await state.get_data()
        restaurant_id = data.get('editing_restaurant_id')
        if restaurant_id:
            from database.queries import get_restaurant_by_id
            restaurant_data = await get_restaurant_by_id(restaurant_id)
            if restaurant_data:
                await message.answer(f'✏️ Редактирование: {restaurant_data.get("restaurant_name")}', reply_markup=get_restaurant_edit_keyboard())
                await state.set_state(BotStates.waiting_restaurant_edit_all)
                return
        await main_menu(message, state)
        return

    if message.text != "✅ Да, удалить":
        await message.answer('Используйте кнопки.', reply_markup=get_delete_confirm_keyboard())
        return

    data = await state.get_data()
    restaurant_id = data.get('editing_restaurant_id')
    restaurant_name = data.get('editing_restaurant_name', 'ресторан')

    if not restaurant_id:
        await message.answer('❌ Ошибка: ресторан не выбран.')
        await main_menu(message, state)
        return

    try:
        success = await delete_restaurant(restaurant_id)
        if success:
            await message.answer(f'✅ Партнёр "{restaurant_name}" удалён!')
        else:
            await message.answer('❌ Ошибка при удалении.')
        await main_menu(message, state)
    except Exception as e:
        await log_error(e, "restaurant_deletion")
        await message.answer('❌ Ошибка при удалении. Попробуйте позже.')
        await main_menu(message, state)


def register_admin_handlers(dp, bot):
    """Регистрация обработчиков для администраторов"""
    dp.message.register(handle_admin_action, StateFilter(
        BotStates.waiting_admin_action))
    dp.message.register(handle_username_input,
                        StateFilter(BotStates.waiting_username))
    dp.message.register(handle_newsletter_input,
                        StateFilter(BotStates.waiting_newsletter))
    dp.message.register(handle_newsletter_confirm, StateFilter(
        BotStates.waiting_newsletter_confirm))
    dp.message.register(handle_restaurant_name_input,
                        StateFilter(BotStates.waiting_restaurant_name))
    dp.message.register(handle_restaurant_address_input,
                        StateFilter(BotStates.waiting_restaurant_address))
    dp.message.register(handle_restaurant_reservation_input,
                        StateFilter(BotStates.waiting_restaurant_reservation))
    dp.message.register(handle_restaurant_delivery_input,
                        StateFilter(BotStates.waiting_restaurant_delivery))
    dp.message.register(handle_restaurant_region_input,
                        StateFilter(BotStates.waiting_restaurant_region))
    dp.message.register(handle_restaurant_category_input,
                        StateFilter(BotStates.waiting_restaurant_category))
    dp.message.register(handle_restaurant_username_input,
                        StateFilter(BotStates.waiting_restaurant_username))
    dp.message.register(handle_restaurant_confirm, StateFilter(
        BotStates.waiting_restaurant_confirm))
    dp.message.register(handle_restaurant_edit_selection, StateFilter(
        BotStates.waiting_restaurant_edit_selection))
    dp.message.register(handle_restaurant_edit_all, StateFilter(
        BotStates.waiting_restaurant_edit_all))
    dp.message.register(handle_restaurant_delete_confirm, StateFilter(
        BotStates.waiting_restaurant_delete_confirm))

    from handlers.restaurant import handle_menu_manager_action, handle_menu_upload
    dp.message.register(handle_menu_manager_action, StateFilter(
        BotStates.waiting_restaurant_menu_manager))
    dp.message.register(handle_menu_upload, StateFilter(
        BotStates.waiting_restaurant_menu_upload))
    dp.message.register(handle_menu_upload, F.document, StateFilter(
        BotStates.waiting_restaurant_menu_upload))

    logger.info("Admin handlers зарегистрированы")
