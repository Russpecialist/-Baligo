"""Обработчики для ресторанов (личный кабинет)"""
import os
from aiogram import F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from config import MENU_PATH, PENDING_MENU_PATH
from database.queries import (
    get_user_restaurants, get_restaurant_by_id, get_restaurant_id_by_name,
    create_approval_request, get_user_approvals, get_all_admin_chat_ids,
    get_approval_request, get_user_role_by_chat_id, add_user_restaurant,
    remove_user_restaurant, get_restaurant_moderators, get_chat_id
)
from utils.keyboards import (
    get_restaurant_cabinet_keyboard, get_edit_fields_keyboard,
    get_back_to_cabinet_keyboard, get_cancel_keyboard
)
from utils.telegram_helpers import get_chat_id_from_username
from utils.helpers import log_error, format_approval_status_message
from utils.pdf_converter import pdf_to_images, clear_cache, save_telegram_document_file_id
from handlers.common import main_menu
from handlers.user import show_regions_or_restaurants
from states.bot_states import BotStates
import logging

logger = logging.getLogger(__name__)

# Маппинг полей для редактирования
FIELD_MAPPING = {
    "Название ресторана": "restaurant_name",
    "Меню": "menu",
    "Бронирование": "reservation",
    "Доставка": "delivery",
    "Регион": "region_nm",
    "Адрес": "address_nm"
}

# Обработчики как отдельные функции
async def handle_restaurant_cabinet(message: Message, state: FSMContext):
    """Обработка действий в личном кабинете ресторана"""
    logger.debug(f"handle_restaurant_cabinet: получено сообщение '{message.text}' от пользователя {message.from_user.id}")
    if message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
        return
    
    if message.text == "🏢 Личный кабинет ресторана":
        # Просто показываем меню кабинета снова
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        return
    
    if message.text == "📝 Редактировать информацию":
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer(
                    "У вас нет привязанных ресторанов. Обратитесь к администратору."
                )
            return
        
        if len(restaurants) == 1:
            await state.update_data(selected_restaurant_id=restaurants[0]['restaurant_id'])
            markup = get_edit_fields_keyboard()
            await message.answer("Выберите поле для редактирования:", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_edit_field)
        else:
            buttons = [[KeyboardButton(text="⬅️ Назад в кабинет")]]
            for r in restaurants:
                buttons.append([KeyboardButton(text=r['restaurant_name'])])
            
            markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            await message.answer("Выберите ресторан для редактирования:", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_selection)
    
    elif message.text == "📊 Статус заявок":
        chat_id = message.chat.id
        approvals = await get_user_approvals(chat_id)
        
        if not approvals:
            await message.answer("У вас нет заявок на изменения.")
            return
        
        for approval in approvals[:10]:
            msg = format_approval_status_message(approval)
            await message.answer(msg)
    
    elif message.text == "👁 Просмотр информации":
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer("У вас нет привязанных ресторанов.")
            return
        
        for r in restaurants:
            restaurant = await get_restaurant_by_id(r['restaurant_id'])
            if restaurant:
                menu_value = restaurant.get('menu')
                menu_str = str(menu_value) if menu_value is not None else 'Не указано'
                if len(menu_str) > 100:
                    menu_str = menu_str[:100] + '...'
                
                info_text = f"""
🏪 {restaurant.get('restaurant_name', 'Неизвестно')}
📍 Адрес: {restaurant.get('address_nm', 'Не указан')}
🌍 Регион: {restaurant.get('region_nm', 'Не указан')}
📞 Бронирование: {restaurant.get('reservation', 'Не указано')}
🚚 Доставка: {restaurant.get('delivery', 'Не указано')}
📋 Меню: {menu_str}
"""
                await message.answer(info_text)
    
    elif message.text == "🏪 Просмотр всех ресторанов":
        await show_regions_or_restaurants(message, state, is_admin=False)
    
    elif message.text == "➕ Добавить модератора":
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer(
                    "У вас нет привязанных ресторанов. Обратитесь к администратору."
                )
            return
        
        if len(restaurants) == 1:
            await state.update_data(
                selected_restaurant_id=restaurants[0]['restaurant_id'],
                action='add_moderator'
            )
            await message.answer(
                "Введите Telegram username (@username) пользователя, которого хотите добавить как модератора:",
                reply_markup=get_cancel_keyboard()
            )
            await state.set_state(BotStates.waiting_moderator_username)
        else:
            buttons = [[KeyboardButton(text="❌ Отменить")]]
            for r in restaurants:
                buttons.append([KeyboardButton(text=r['restaurant_name'])])
            
            markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            await state.update_data(action='add_moderator')
            await message.answer("Выберите ресторан для добавления модератора:", reply_markup=markup)
            await state.set_state(BotStates.waiting_moderator_restaurant_selection)
    
    elif message.text == "➖ Удалить модератора":
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer(
                    "У вас нет привязанных ресторанов. Обратитесь к администратору."
                )
            return
        
        if len(restaurants) == 1:
            restaurant_id = restaurants[0]['restaurant_id']
            await show_moderator_removal_selection(message, state, restaurant_id)
        else:
            buttons = [[KeyboardButton(text="❌ Отменить")]]
            for r in restaurants:
                buttons.append([KeyboardButton(text=r['restaurant_name'])])
            
            markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            await state.update_data(action='remove_moderator')
            await message.answer("Выберите ресторан для удаления модератора:", reply_markup=markup)
            await state.set_state(BotStates.waiting_moderator_restaurant_selection)
    
    elif message.text == "🎁 Изменить Акции":
        # Обработка кнопки "Изменить Акции"
        logger.info(f"Обработка кнопки 'Изменить Акции' для пользователя {message.from_user.id}")
        from handlers.promotions_events import handle_promotions_start
        await handle_promotions_start(message, state)
        return
    
    elif message.text == "🎊 Изменить События":
        # Обработка кнопки "Изменить События"
        logger.info(f"Обработка кнопки 'Изменить События' для пользователя {message.from_user.id}")
        from handlers.promotions_events import handle_events_start
        await handle_events_start(message, state)
        return
    
    elif message.text == "🎉 Изменить банкет":
        # Обработка кнопки "Изменить банкет"
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer(
                    "У вас нет привязанных ресторанов. Обратитесь к администратору."
                )
            return
        
        if len(restaurants) == 1:
            restaurant_id = restaurants[0]['restaurant_id']
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                restaurant_name = restaurant.get('restaurant_name', '')
                banquet_folder = os.path.join(MENU_PATH, restaurant_name, "Банкет")
                await state.update_data(
                    banquet_folder=banquet_folder,
                    selected_restaurant_id=restaurant_id,
                    restaurant_name=restaurant_name
                )
                await show_banquet_manager(message, state, banquet_folder)
            else:
                await message.answer("Ошибка получения информации о ресторане.")
        else:
            buttons = [[KeyboardButton(text="⬅️ Назад в кабинет")]]
            for r in restaurants:
                buttons.append([KeyboardButton(text=r['restaurant_name'])])
            
            markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            await state.update_data(action='banquet')
            await message.answer("Выберите ресторан для управления банкетами:", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_selection)
        return
    
    elif message.text == "📋 Изменить меню":
        # Обработка кнопки "Изменить меню"
        chat_id = message.chat.id
        role, status = await get_user_role_by_chat_id(chat_id)
        is_admin = (role == 'admin' and status == 'active')
        
        # Если админ, показываем все рестораны; иначе только свои
        if is_admin:
            from database.queries import get_all_restaurants
            all_restaurants = await get_all_restaurants()
            restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
        else:
            restaurants = await get_user_restaurants(chat_id)
        
        if not restaurants:
            if is_admin:
                await message.answer("В системе нет ресторанов.")
            else:
                await message.answer(
                    "У вас нет привязанных ресторанов. Обратитесь к администратору."
                )
            return
        
        if len(restaurants) == 1:
            restaurant_id = restaurants[0]['restaurant_id']
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                restaurant_name = restaurant.get('restaurant_name', '')
                menu_folder = os.path.join(MENU_PATH, restaurant_name)
                os.makedirs(menu_folder, exist_ok=True)
                await state.update_data(
                    menu_folder=menu_folder,
                    selected_restaurant_id=restaurant_id,
                    restaurant_name=restaurant_name
                )
                await show_menu_manager(message, state, menu_folder)
            else:
                await message.answer("Ошибка получения информации о ресторане.")
        else:
            buttons = [[KeyboardButton(text="⬅️ Назад в кабинет")]]
            for r in restaurants:
                buttons.append([KeyboardButton(text=r['restaurant_name'])])
            
            markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            await state.update_data(action='menu')
            await message.answer("Выберите ресторан для управления меню:", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_selection)
        return
    
    else:
        await message.answer("Неизвестная команда. Выберите из предложенных вариантов.")

async def handle_restaurant_selection(message: Message, state: FSMContext):
    """Обработка выбора ресторана для редактирования"""
    if message.text == "⬅️ Назад в кабинет":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    chat_id = message.chat.id
    role, status = await get_user_role_by_chat_id(chat_id)
    is_admin = (role == 'admin' and status == 'active')
    
    # Если админ, показываем все рестораны; иначе только свои
    if is_admin:
        from database.queries import get_all_restaurants
        all_restaurants = await get_all_restaurants()
        restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
    else:
        restaurants = await get_user_restaurants(chat_id)
    
    restaurant_name = message.text
    selected_restaurant = None
    for r in restaurants:
        if r['restaurant_name'] == restaurant_name:
            selected_restaurant = r
            break
    
    if not selected_restaurant:
        await message.answer("Ресторан не найден. Выберите из списка.")
        return
    
    restaurant_id = selected_restaurant['restaurant_id']
    await state.update_data(selected_restaurant_id=restaurant_id)
    
    # Проверяем, для чего был выбран ресторан
    state_data = await state.get_data()
    action = state_data.get('action')
    
    if action == 'promotions':
        # Показываем список акций
        from handlers.promotions_events import show_promotions_list
        await show_promotions_list(message, state, restaurant_id)
    elif action == 'events':
        # Показываем список событий
        from handlers.promotions_events import show_events_list
        await show_events_list(message, state, restaurant_id)
    elif action == 'banquet':
        # Показываем менеджер банкетов
        restaurant = await get_restaurant_by_id(restaurant_id)
        if restaurant:
            restaurant_name = restaurant.get('restaurant_name', '')
            banquet_folder = os.path.join(MENU_PATH, restaurant_name, "Банкет")
            await state.update_data(
                banquet_folder=banquet_folder,
                selected_restaurant_id=restaurant_id,
                restaurant_name=restaurant_name
            )
            await show_banquet_manager(message, state, banquet_folder)
        else:
            await message.answer("Ошибка получения информации о ресторане.")
    elif action == 'menu':
        # Показываем менеджер меню
        restaurant = await get_restaurant_by_id(restaurant_id)
        if restaurant:
            restaurant_name = restaurant.get('restaurant_name', '')
            menu_folder = os.path.join(MENU_PATH, restaurant_name)
            os.makedirs(menu_folder, exist_ok=True)
            await state.update_data(
                menu_folder=menu_folder,
                selected_restaurant_id=restaurant_id,
                restaurant_name=restaurant_name
            )
            await show_menu_manager(message, state, menu_folder)
        else:
            await message.answer("Ошибка получения информации о ресторане.")
    else:
        # Обычное редактирование
        markup = get_edit_fields_keyboard()
        await message.answer("Выберите поле для редактирования:", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_edit_field)

async def handle_edit_field_selection(message: Message, state: FSMContext):
    """Обработка выбора поля для редактирования"""
    if message.text == "⬅️ Назад в кабинет":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    field_name_ru = message.text
    field_name = FIELD_MAPPING.get(field_name_ru)
    
    if not field_name:
        await message.answer("Неизвестное поле. Выберите из предложенных вариантов.")
        return
    
    await state.update_data(selected_field=field_name, selected_field_ru=field_name_ru)
    
    data = await state.get_data()
    restaurant_id = data.get('selected_restaurant_id')
    restaurant = await get_restaurant_by_id(restaurant_id)
    
    if restaurant:
        current_value = restaurant.get(field_name, 'Не указано')
        # Показываем клавиатуру с кнопкой "Назад в кабинет" при запросе нового значения
        markup = get_back_to_cabinet_keyboard()
        await message.answer(
            f"Текущее значение поля '{field_name_ru}':\n{current_value}\n\n"
            f"Введите новое значение:",
            reply_markup=markup
        )
    else:
        await message.answer("Ошибка получения информации о ресторане.")
        return
    
    if field_name == "menu":
        # Показываем файловый менеджер для меню ресторана
        restaurant_name = restaurant.get('restaurant_name', '')
        menu_folder = os.path.join(MENU_PATH, restaurant_name)
        
        # Создаем папку, если её нет
        os.makedirs(menu_folder, exist_ok=True)
        
        # Сохраняем все необходимые данные в state, включая restaurant_id
        await state.update_data(
            menu_folder=menu_folder,
            restaurant_name=restaurant_name,
            selected_restaurant_id=restaurant_id  # Важно сохранить restaurant_id
        )
        await show_menu_manager(message, state, menu_folder)
    else:
        await state.set_state(BotStates.waiting_restaurant_edit_value)

async def handle_edit_value_input(message: Message, state: FSMContext):
    """Обработка ввода нового значения"""
    if message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
        return
    
    if message.text == "⬅️ Назад в кабинет":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    data = await state.get_data()
    restaurant_id = data.get('selected_restaurant_id')
    field_name = data.get('selected_field')
    field_name_ru = data.get('selected_field_ru')
    new_value = message.text
    
    restaurant = await get_restaurant_by_id(restaurant_id)
    if not restaurant:
        await message.answer("Ошибка получения информации о ресторане.")
        return
    
    old_value = str(restaurant.get(field_name, ''))
    
    approval_id = await create_approval_request(
        restaurant_id=restaurant_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        requested_by=message.chat.id
    )
    
    if approval_id:
        admin_chat_ids = await get_all_admin_chat_ids()
        from utils.helpers import format_approval_message, send_approval_notification
        from utils.keyboards import get_approval_keyboard
        
        approval = await get_approval_request(approval_id)
        if approval:
            msg_text = format_approval_message(approval)
            markup = get_approval_keyboard(approval_id)
            bot = message.bot
            
            # Отправляем уведомление с кнопкой "Показать"
            restaurant_name = restaurant.get('restaurant_name', 'Неизвестный ресторан')
            await send_approval_notification(bot, admin_chat_ids, restaurant_name)
            
            # Отправляем детальное сообщение с кнопками подтверждения/отклонения
            for admin_id in admin_chat_ids:
                try:
                    await bot.send_message(admin_id, msg_text, reply_markup=markup)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        await message.answer(
            f"✅ Запрос на изменение поля '{field_name_ru}' отправлен на согласование.\n"
            f"Вы получите уведомление после рассмотрения заявки."
        )
        
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
    else:
        await message.answer("❌ Ошибка создания запроса на согласование.")

async def show_menu_manager(message: Message, state: FSMContext, menu_folder: str):
    """Показать файловый менеджер для меню ресторана"""
    try:
        if not os.path.exists(menu_folder):
            os.makedirs(menu_folder, exist_ok=True)
        
        items = []
        try:
            for item in sorted(os.listdir(menu_folder)):
                item_path = os.path.join(menu_folder, item)
                if os.path.isfile(item_path) and item.lower().endswith('.pdf'):
                    items.append(("📄", item, "file"))
        except PermissionError:
            await message.answer("Нет доступа к папке меню.")
            return
        
        buttons = []
        buttons.append([KeyboardButton(text="📤 Загрузить PDF")])
        
        for icon, name, item_type in items:
            button_text = f"{icon} {name}"
            buttons.append([KeyboardButton(text=button_text)])
        
        buttons.append([KeyboardButton(text="⬅️ Назад в кабинет")])
        
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        
        await message.answer(
            f"📁 Управление меню ресторана\n"
            f"📊 Файлов: {len(items)}\n\n"
            "Выберите действие:",
            reply_markup=markup
        )
        
        await state.set_state(BotStates.waiting_restaurant_menu_manager)
        
    except Exception as e:
        await log_error(e, f"menu_manager_show_{menu_folder}")
        await message.answer("Ошибка при отображении менеджера меню.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)

async def handle_menu_manager_action(message: Message, state: FSMContext):
    """Обработка действий в менеджере меню"""
    data = await state.get_data()
    menu_folder = data.get('menu_folder')
    restaurant_name = data.get('restaurant_name', '')
    
    if not menu_folder:
        await message.answer("Ошибка: папка меню не определена.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    try:
        if message.text == "⬅️ Назад в кабинет":
            # Проверяем роль пользователя
            role, status = await get_user_role_by_chat_id(message.chat.id)
            if role == 'admin' and status == 'active':
                # Возвращаем админа в админ-меню
                await main_menu(message, state)
            else:
                # Возвращаем ресторан в личный кабинет
                markup = get_restaurant_cabinet_keyboard()
                await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                await state.set_state(BotStates.waiting_restaurant_cabinet)
            return
        
        elif message.text == "📤 Загрузить PDF":
            await message.answer(
                "📤 Загрузка PDF меню\n\n"
                "Отправьте PDF файл для загрузки.\n"
                "⚠️ Разрешены только PDF файлы!"
            )
            await state.set_state(BotStates.waiting_restaurant_menu_upload)
            return
        
        elif message.text.startswith("📄 "):
            file_name = message.text[2:].strip()
            file_path = os.path.join(menu_folder, file_name)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_size_mb = round(file_size / (1024 * 1024), 2)
                
                buttons = [
                    [KeyboardButton(text="🔄 Заменить файл")],
                    [KeyboardButton(text="🗑️ Удалить файл")],
                    [KeyboardButton(text="⬅️ Назад к списку")]
                ]
                markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
                
                await message.answer(
                    f"📄 Файл: {file_name}\n"
                    f"📊 Размер: {file_size_mb} MB\n\n"
                    "Что хотите сделать с файлом?",
                    reply_markup=markup
                )
                
                # Сохраняем данные о файле и убеждаемся, что restaurant_id сохранен
                data = await state.get_data()
                restaurant_id = data.get('selected_restaurant_id')
                if not restaurant_id:
                    # Пытаемся получить restaurant_id из restaurant_name
                    from database.queries import get_restaurant_id_by_name
                    if restaurant_name:
                        restaurant_id = await get_restaurant_id_by_name(restaurant_name)
                
                await state.update_data(
                    selected_file=file_path,
                    selected_file_name=file_name,
                    selected_restaurant_id=restaurant_id,
                    menu_folder=menu_folder  # Обновляем на всякий случай
                )
            else:
                await message.answer("Файл не найден.")
            return
        
        elif message.text == "🔄 Заменить файл":
            # Убеждаемся, что все необходимые данные есть в state
            data = await state.get_data()
            restaurant_id = data.get('selected_restaurant_id')
            
            # Если restaurant_id не найден, пытаемся получить его из restaurant_name
            if not restaurant_id:
                if restaurant_name:
                    from database.queries import get_restaurant_id_by_name
                    restaurant_id = await get_restaurant_id_by_name(restaurant_name)
            
            if not restaurant_id:
                logger.error(f"restaurant_id не найден для пользователя {message.chat.id}, restaurant_name={restaurant_name}")
                await message.answer("❌ Ошибка: ресторан не выбран.")
                # Проверяем роль пользователя
                role, status = await get_user_role_by_chat_id(message.chat.id)
                if role == 'admin' and status == 'active':
                    # Возвращаем админа в админ-меню
                    await main_menu(message, state)
                else:
                    # Возвращаем ресторан в личный кабинет
                    markup = get_restaurant_cabinet_keyboard()
                    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                    await state.set_state(BotStates.waiting_restaurant_cabinet)
                return
            
            # Обновляем state с необходимыми данными (на случай, если они были потеряны)
            await state.update_data(
                menu_folder=menu_folder,
                selected_restaurant_id=restaurant_id,
                restaurant_name=restaurant_name  # Сохраняем на всякий случай
            )
            
            await message.answer(
                f"🔄 Замена файла\n\n"
                "Отправьте новый PDF файл для замены текущего.\n"
                "⚠️ Разрешены только PDF файлы!"
            )
            await state.set_state(BotStates.waiting_restaurant_menu_upload)
            return
        
        elif message.text == "🗑️ Удалить файл":
            data = await state.get_data()
            file_path = data.get('selected_file')
            file_name = data.get('selected_file_name')
            
            if file_path and os.path.exists(file_path):
                try:
                    # Удаляем кэш перед удалением файла
                    clear_cache(file_path)
                    
                    os.remove(file_path)
                    await message.answer(f"✅ Файл {file_name} успешно удален. Кэш очищен.")
                except Exception as e:
                    await log_error(e, f"menu_file_delete_{file_path}")
                    await message.answer(f"❌ Ошибка при удалении файла: {str(e)}")
            else:
                await message.answer("Файл не найден.")
            
            await show_menu_manager(message, state, menu_folder)
            return
        
        elif message.text == "⬅️ Назад к списку":
            await show_menu_manager(message, state, menu_folder)
            return
        
        else:
            await message.answer("Неизвестная команда. Выберите действие из меню.")
    
    except Exception as e:
        await log_error(e, f"menu_manager_action_{message.text}")
        await message.answer("Произошла ошибка при обработке команды.")
        await show_menu_manager(message, state, menu_folder)

async def handle_menu_upload(message: Message, state: FSMContext):
    """Обработка загрузки PDF меню"""
    data = await state.get_data()
    menu_folder = data.get('menu_folder')
    restaurant_id = data.get('selected_restaurant_id')
    selected_file = data.get('selected_file')
    bot = message.bot
    
    # Проверяем роль пользователя
    role, status = await get_user_role_by_chat_id(message.chat.id)
    is_admin = (role == 'admin' and status == 'active')
    
    # Обработка кнопки "Назад к списку"
    if message.text == "⬅️ Назад к списку":
        if menu_folder:
            await show_menu_manager(message, state, menu_folder)
        else:
            # Проверяем роль пользователя
            role, status = await get_user_role_by_chat_id(message.chat.id)
            if role == 'admin' and status == 'active':
                # Возвращаем админа в админ-меню
                await main_menu(message, state)
            else:
                # Возвращаем ресторан в личный кабинет
                markup = get_restaurant_cabinet_keyboard()
                await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    if not menu_folder:
        logger.error(f"menu_folder не определен в state для пользователя {message.chat.id}")
        await message.answer("Ошибка: папка меню не определена.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    if not restaurant_id:
        logger.error(f"restaurant_id не определен в state для пользователя {message.chat.id}")
        await message.answer("Ошибка: ресторан не выбран.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    try:
        if message.document:
            # Проверяем формат файла
            file_name = message.document.file_name or f"file_{message.document.file_id}"
            
            if not file_name.lower().endswith('.pdf'):
                await message.answer(
                    "❌ Ошибка: разрешены только PDF файлы!\n"
                    "Пожалуйста, отправьте файл с расширением .pdf"
                )
                return
            
            if message.document.file_size > 50 * 1024 * 1024:
                await message.answer("❌ Файл слишком большой (максимум 50MB).")
                return
            
            # Отправляем сообщение о начале загрузки
            loading_msg = await message.answer("⏳ Файл загружается, пожалуйста подождите...")
            
            # Для меню всегда сохраняем во временную папку до согласования
            # Определяем путь к старому файлу (если есть)
            old_file_path = None
            old_file_name = None
            if selected_file and os.path.exists(selected_file):
                old_file_path = selected_file
                old_file_name = os.path.basename(selected_file)
                # При замене используем имя старого файла
                file_name = old_file_name
                action = "заменен"
                logger.info(f"Замена файла: {selected_file}, новое имя будет: {file_name}")
            else:
                # Проверяем, есть ли уже файл с таким именем в rest_menu
                existing_file_path = os.path.join(menu_folder, file_name)
                if os.path.exists(existing_file_path):
                    old_file_path = existing_file_path
                    old_file_name = os.path.basename(existing_file_path)
                    # При замене используем имя существующего файла
                    file_name = old_file_name
                    action = "заменен"
                    logger.info(f"Замена существующего файла: {existing_file_path}, новое имя будет: {file_name}")
                else:
                    action = "загружен"
                    logger.info(f"Новая загрузка файла: {file_name}")
            
            # Сохраняем во временную папку
            pending_dir = os.path.join(PENDING_MENU_PATH, str(restaurant_id))
            os.makedirs(pending_dir, exist_ok=True)
            save_path = os.path.join(pending_dir, file_name)
            
            try:
                logger.info(f"Сохранение файла в: {save_path}")
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file_info = await bot.get_file(message.document.file_id)
                await bot.download_file(file_info.file_path, save_path)
                logger.info(f"Файл успешно сохранен: {save_path}")
                
                # Сохраняем file_id документа для кэширования
                save_telegram_document_file_id(save_path, message.document.file_id)
                
                # Удаляем сообщение о загрузке
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                restaurant = await get_restaurant_by_id(restaurant_id)
                if not restaurant:
                    logger.error(f"Ресторан {restaurant_id} не найден в БД")
                    await message.answer("❌ Ошибка: ресторан не найден в базе данных.")
                    await show_menu_manager(message, state, menu_folder)
                    return
                
                # Все изменения (включая админа) отправляются на согласование
                # Определяем старое значение
                if old_file_path:
                    old_value = os.path.basename(old_file_path)
                else:
                    old_value = str(restaurant.get('menu', '') or 'Нет файла')
                
                logger.info(f"Создание запроса на согласование: restaurant_id={restaurant_id}, old_value={old_value}, new_value={file_name}")
                
                approval_id = await create_approval_request(
                    restaurant_id=restaurant_id,
                    field_name='menu',
                    old_value=old_value,
                    new_value=file_name,
                    requested_by=message.chat.id,
                    temp_file_path=save_path  # Сохраняем путь к временному файлу
                )
                
                if approval_id:
                    admin_chat_ids = await get_all_admin_chat_ids()
                    from utils.helpers import send_menu_approval_message, send_approval_notification
                    from utils.keyboards import get_approval_keyboard
                    
                    approval = await get_approval_request(approval_id)
                    if approval:
                        markup = get_approval_keyboard(approval_id)
                        
                        # Отправляем уведомление с кнопкой "Показать"
                        restaurant_name = restaurant.get('restaurant_name', 'Неизвестный ресторан')
                        await send_approval_notification(bot, admin_chat_ids, restaurant_name)
                        
                        # Отправляем сообщение с файлами админам
                        for admin_id in admin_chat_ids:
                            try:
                                await send_menu_approval_message(
                                    bot, admin_id, approval, old_file_path, save_path
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
                    await message.answer(
                        f"✅ PDF файл {file_name} загружен и отправлен на согласование!\n"
                        f"📊 Размер: {round(message.document.file_size / (1024 * 1024), 2)} MB\n"
                        f"⏳ Ожидайте подтверждения администратора."
                    )
                else:
                    logger.error(f"Не удалось создать запрос на согласование для restaurant_id={restaurant_id}")
                    await message.answer("❌ Ошибка создания запроса на согласование.")
                
                await show_menu_manager(message, state, menu_folder)
                
            except Exception as e:
                logger.error(f"Ошибка при сохранении файла {file_name}: {e}", exc_info=True)
                await log_error(e, f"menu_file_download_{file_name}")
                await message.answer(f"❌ Ошибка при сохранении файла: {str(e)}")
                # Пытаемся вернуться в менеджер меню
                try:
                    await show_menu_manager(message, state, menu_folder)
                except:
                    pass
        
        else:
            await message.answer(
                "❌ Пожалуйста, отправьте PDF файл.\n"
                "Используйте кнопку '⬅️ Назад к списку' для возврата."
            )
    
    except Exception as e:
        logger.error(f"Критическая ошибка в handle_menu_upload: {e}", exc_info=True)
        await log_error(e, f"menu_upload_handler")
        await message.answer("Произошла ошибка при обработке загрузки.")
        # Пытаемся вернуться в менеджер меню или кабинет
        try:
            if menu_folder:
                await show_menu_manager(message, state, menu_folder)
            else:
                # Проверяем роль пользователя
                role, status = await get_user_role_by_chat_id(message.chat.id)
                if role == 'admin' and status == 'active':
                    # Возвращаем админа в админ-меню
                    await main_menu(message, state)
                else:
                    # Возвращаем ресторан в личный кабинет
                    markup = get_restaurant_cabinet_keyboard()
                    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                    await state.set_state(BotStates.waiting_restaurant_cabinet)
        except Exception as e2:
            logger.error(f"Ошибка при возврате в меню: {e2}")

async def show_banquet_manager(message: Message, state: FSMContext, banquet_folder: str):
    """Показать файловый менеджер для банкетов ресторана"""
    try:
        if not os.path.exists(banquet_folder):
            os.makedirs(banquet_folder, exist_ok=True)
        
        items = []
        try:
            for item in sorted(os.listdir(banquet_folder)):
                item_path = os.path.join(banquet_folder, item)
                if os.path.isfile(item_path) and item.lower().endswith('.pdf'):
                    items.append(("📄", item, "file"))
        except PermissionError:
            await message.answer("Нет доступа к папке банкетов.")
            return
        
        buttons = []
        buttons.append([KeyboardButton(text="📤 Загрузить PDF")])
        
        for icon, name, item_type in items:
            button_text = f"{icon} {name}"
            buttons.append([KeyboardButton(text=button_text)])
        
        buttons.append([KeyboardButton(text="⬅️ Назад в кабинет")])
        
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        
        await message.answer(
            f"🎉 Управление банкетами ресторана\n"
            f"📊 Файлов: {len(items)}\n\n"
            "Выберите действие:",
            reply_markup=markup
        )
        
        await state.set_state(BotStates.waiting_restaurant_banquet_manager)
        
    except Exception as e:
        await log_error(e, f"banquet_manager_show_{banquet_folder}")
        await message.answer("Ошибка при отображении менеджера банкетов.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)

async def handle_banquet_manager_action(message: Message, state: FSMContext):
    """Обработка действий в менеджере банкетов"""
    data = await state.get_data()
    banquet_folder = data.get('banquet_folder')
    restaurant_name = data.get('restaurant_name', '')
    
    if not banquet_folder:
        await message.answer("Ошибка: папка банкетов не определена.")
        # Проверяем роль пользователя
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            # Возвращаем админа в админ-меню
            await main_menu(message, state)
        else:
            # Возвращаем ресторан в личный кабинет
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    try:
        if message.text == "⬅️ Назад в кабинет":
            # Проверяем роль пользователя
            role, status = await get_user_role_by_chat_id(message.chat.id)
            if role == 'admin' and status == 'active':
                # Возвращаем админа в админ-меню
                await main_menu(message, state)
            else:
                # Возвращаем ресторан в личный кабинет
                markup = get_restaurant_cabinet_keyboard()
                await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                await state.set_state(BotStates.waiting_restaurant_cabinet)
            return
        
        elif message.text == "📤 Загрузить PDF":
            await message.answer(
                "📤 Загрузка PDF банкета\n\n"
                "Отправьте PDF файл для загрузки.\n"
                "⚠️ Разрешены только PDF файлы!"
            )
            await state.set_state(BotStates.waiting_restaurant_banquet_upload)
            return
        
        elif message.text.startswith("📄 "):
            file_name = message.text[2:].strip()
            file_path = os.path.join(banquet_folder, file_name)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_size_mb = round(file_size / (1024 * 1024), 2)
                
                buttons = [
                    [KeyboardButton(text="🔄 Заменить файл")],
                    [KeyboardButton(text="🗑️ Удалить файл")],
                    [KeyboardButton(text="⬅️ Назад к списку")]
                ]
                markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
                
                await message.answer(
                    f"📄 Файл: {file_name}\n"
                    f"📊 Размер: {file_size_mb} MB\n\n"
                    "Что хотите сделать с файлом?",
                    reply_markup=markup
                )
                
                # Сохраняем данные о файле
                data = await state.get_data()
                restaurant_id = data.get('selected_restaurant_id')
                if not restaurant_id:
                    from database.queries import get_restaurant_id_by_name
                    if restaurant_name:
                        restaurant_id = await get_restaurant_id_by_name(restaurant_name)
                
                await state.update_data(
                    selected_file=file_path,
                    selected_file_name=file_name,
                    selected_restaurant_id=restaurant_id,
                    banquet_folder=banquet_folder
                )
            else:
                await message.answer("Файл не найден.")
            return
        
        elif message.text == "🔄 Заменить файл":
            data = await state.get_data()
            restaurant_id = data.get('selected_restaurant_id')
            
            if not restaurant_id:
                if restaurant_name:
                    from database.queries import get_restaurant_id_by_name
                    restaurant_id = await get_restaurant_id_by_name(restaurant_name)
            
            if not restaurant_id:
                logger.error(f"restaurant_id не найден для пользователя {message.chat.id}, restaurant_name={restaurant_name}")
                await message.answer("❌ Ошибка: ресторан не выбран.")
                role, status = await get_user_role_by_chat_id(message.chat.id)
                if role == 'admin' and status == 'active':
                    await main_menu(message, state)
                else:
                    markup = get_restaurant_cabinet_keyboard()
                    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                    await state.set_state(BotStates.waiting_restaurant_cabinet)
                return
            
            # Обновляем state с необходимыми данными
            await state.update_data(
                banquet_folder=banquet_folder,
                selected_restaurant_id=restaurant_id,
                restaurant_name=restaurant_name
            )
            
            await message.answer(
                f"🔄 Замена файла\n\n"
                "Отправьте новый PDF файл для замены текущего.\n"
                "⚠️ Разрешены только PDF файлы!"
            )
            await state.set_state(BotStates.waiting_restaurant_banquet_upload)
            return
        
        elif message.text == "🗑️ Удалить файл":
            data = await state.get_data()
            file_path = data.get('selected_file')
            file_name = data.get('selected_file_name')
            
            if file_path and os.path.exists(file_path):
                try:
                    # Удаляем кэш перед удалением файла
                    clear_cache(file_path)
                    
                    os.remove(file_path)
                    await message.answer(f"✅ Файл {file_name} успешно удален. Кэш очищен.")
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {file_name}: {e}")
                    await message.answer(f"❌ Ошибка при удалении файла: {str(e)}")
            else:
                await message.answer("Файл не найден.")
            
            # Возвращаемся к списку файлов
            await show_banquet_manager(message, state, banquet_folder)
            return
        
        elif message.text == "⬅️ Назад к списку":
            if banquet_folder:
                await show_banquet_manager(message, state, banquet_folder)
            else:
                role, status = await get_user_role_by_chat_id(message.chat.id)
                if role == 'admin' and status == 'active':
                    await main_menu(message, state)
                else:
                    markup = get_restaurant_cabinet_keyboard()
                    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                    await state.set_state(BotStates.waiting_restaurant_cabinet)
            return
        
        else:
            await message.answer("Неизвестная команда. Выберите из предложенных вариантов.")
            
    except Exception as e:
        logger.error(f"Ошибка в handle_banquet_manager_action: {e}", exc_info=True)
        await log_error(e, f"banquet_manager_action")
        await message.answer("Произошла ошибка при обработке действия.")
        try:
            await show_banquet_manager(message, state, banquet_folder)
        except:
            pass

async def handle_banquet_upload(message: Message, state: FSMContext):
    """Обработка загрузки банкетного PDF файла"""
    data = await state.get_data()
    banquet_folder = data.get('banquet_folder')
    restaurant_id = data.get('selected_restaurant_id')
    restaurant_name = data.get('restaurant_name', '')
    selected_file = data.get('selected_file')
    
    if not banquet_folder:
        logger.error(f"banquet_folder не определен в state для пользователя {message.chat.id}")
        await message.answer("Ошибка: папка банкетов не определена.")
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            await main_menu(message, state)
        else:
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    if not restaurant_id:
        logger.error(f"restaurant_id не определен в state для пользователя {message.chat.id}")
        await message.answer("Ошибка: ресторан не выбран.")
        role, status = await get_user_role_by_chat_id(message.chat.id)
        if role == 'admin' and status == 'active':
            await main_menu(message, state)
        else:
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    try:
        if message.document:
            # Проверяем формат файла
            file_name = message.document.file_name or f"file_{message.document.file_id}"
            
            if not file_name.lower().endswith('.pdf'):
                await message.answer(
                    "❌ Ошибка: разрешены только PDF файлы!\n"
                    "Пожалуйста, отправьте файл с расширением .pdf"
                )
                return
            
            if message.document.file_size > 50 * 1024 * 1024:
                await message.answer("❌ Файл слишком большой (максимум 50MB).")
                return
            
            # Отправляем сообщение о начале загрузки
            loading_msg = await message.answer("⏳ Файл загружается, пожалуйста подождите...")
            
            # Определяем путь к старому файлу (если есть)
            old_file_path = None
            old_file_name = None
            if selected_file and os.path.exists(selected_file):
                old_file_path = selected_file
                old_file_name = os.path.basename(selected_file)
                # При замене используем имя старого файла
                file_name = old_file_name
                action = "заменен"
                logger.info(f"Замена банкетного файла: {selected_file}, новое имя будет: {file_name}")
            else:
                # Проверяем, есть ли уже файл с таким именем
                existing_file_path = os.path.join(banquet_folder, file_name)
                if os.path.exists(existing_file_path):
                    old_file_path = existing_file_path
                    old_file_name = os.path.basename(existing_file_path)
                    # При замене используем имя существующего файла
                    file_name = old_file_name
                    action = "заменен"
                    logger.info(f"Замена существующего банкетного файла: {existing_file_path}, новое имя будет: {file_name}")
                else:
                    action = "загружен"
                    logger.info(f"Новая загрузка банкетного файла: {file_name}")
            
            # Сохраняем во временную папку
            pending_dir = os.path.join(PENDING_MENU_PATH, str(restaurant_id), "banquet")
            os.makedirs(pending_dir, exist_ok=True)
            save_path = os.path.join(pending_dir, file_name)
            
            try:
                logger.info(f"Сохранение банкетного файла в: {save_path}")
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                bot = message.bot
                file_info = await bot.get_file(message.document.file_id)
                await bot.download_file(file_info.file_path, save_path)
                logger.info(f"Банкетный файл успешно сохранен: {save_path}")
                
                # Сохраняем file_id документа для кэширования
                save_telegram_document_file_id(save_path, message.document.file_id)
                
                # Удаляем сообщение о загрузке
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                restaurant = await get_restaurant_by_id(restaurant_id)
                if not restaurant:
                    logger.error(f"Ресторан {restaurant_id} не найден в БД")
                    await message.answer("❌ Ошибка: ресторан не найден в базе данных.")
                    await show_banquet_manager(message, state, banquet_folder)
                    return
                
                # Все изменения (включая админа) отправляются на согласование
                # Определяем старое значение
                if old_file_path:
                    old_value = os.path.basename(old_file_path)
                else:
                    old_value = "Нет файла"
                
                logger.info(f"Создание запроса на согласование банкета: restaurant_id={restaurant_id}, old_value={old_value}, new_value={file_name}")
                
                approval_id = await create_approval_request(
                    restaurant_id=restaurant_id,
                    field_name='banquet',
                    old_value=old_value,
                    new_value=file_name,
                    requested_by=message.chat.id,
                    temp_file_path=save_path
                )
                
                if approval_id:
                    admin_chat_ids = await get_all_admin_chat_ids()
                    from utils.helpers import send_menu_approval_message, send_approval_notification
                    from utils.keyboards import get_approval_keyboard
                    
                    approval = await get_approval_request(approval_id)
                    if approval:
                        markup = get_approval_keyboard(approval_id)
                        
                        # Отправляем уведомление с кнопкой "Показать"
                        restaurant_name = restaurant.get('restaurant_name', 'Неизвестный ресторан')
                        await send_approval_notification(bot, admin_chat_ids, restaurant_name)
                        
                        # Отправляем сообщение с файлами админам
                        for admin_id in admin_chat_ids:
                            try:
                                await send_menu_approval_message(
                                    bot, admin_id, approval, old_file_path, save_path
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
                    await message.answer(
                        f"✅ PDF файл банкета {file_name} загружен и отправлен на согласование!\n"
                        f"📊 Размер: {round(message.document.file_size / (1024 * 1024), 2)} MB\n"
                        f"⏳ Ожидайте подтверждения администратора."
                    )
                else:
                    logger.error(f"Не удалось создать запрос на согласование банкета для restaurant_id={restaurant_id}")
                    await message.answer("❌ Ошибка создания запроса на согласование.")
                
                await show_banquet_manager(message, state, banquet_folder)
                
            except Exception as e:
                logger.error(f"Ошибка при сохранении банкетного файла {file_name}: {e}", exc_info=True)
                await log_error(e, f"banquet_file_download_{file_name}")
                await message.answer(f"❌ Ошибка при сохранении файла: {str(e)}")
                try:
                    await show_banquet_manager(message, state, banquet_folder)
                except:
                    pass
        
        else:
            await message.answer(
                "❌ Пожалуйста, отправьте PDF файл.\n"
                "Используйте кнопку '⬅️ Назад к списку' для возврата."
            )
    
    except Exception as e:
        logger.error(f"Критическая ошибка в handle_banquet_upload: {e}", exc_info=True)
        await log_error(e, f"banquet_upload_handler")
        await message.answer("Произошла ошибка при обработке загрузки.")
        try:
            if banquet_folder:
                await show_banquet_manager(message, state, banquet_folder)
            else:
                role, status = await get_user_role_by_chat_id(message.chat.id)
                if role == 'admin' and status == 'active':
                    await main_menu(message, state)
                else:
                    markup = get_restaurant_cabinet_keyboard()
                    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
                    await state.set_state(BotStates.waiting_restaurant_cabinet)
        except:
            pass

async def handle_moderator_restaurant_selection(message: Message, state: FSMContext):
    """Обработка выбора ресторана для управления модераторами"""
    if message.text == "❌ Отменить":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    data = await state.get_data()
    action = data.get('action')  # 'add_moderator' или 'remove_moderator'
    
    chat_id = message.chat.id
    role, status = await get_user_role_by_chat_id(chat_id)
    is_admin = (role == 'admin' and status == 'active')
    
    # Если админ, показываем все рестораны; иначе только свои
    if is_admin:
        from database.queries import get_all_restaurants
        all_restaurants = await get_all_restaurants()
        restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
    else:
        restaurants = await get_user_restaurants(chat_id)
    
    restaurant_name = message.text
    selected_restaurant = None
    for r in restaurants:
        if r['restaurant_name'] == restaurant_name:
            selected_restaurant = r
            break
    
    if not selected_restaurant:
        await message.answer("Ресторан не найден. Выберите из предложенных вариантов.")
        return
    
    restaurant_id = selected_restaurant['restaurant_id']
    
    if action == 'add_moderator':
        await state.update_data(selected_restaurant_id=restaurant_id)
        await message.answer(
            "Введите Telegram username (@username) пользователя, которого хотите добавить как модератора:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(BotStates.waiting_moderator_username)
    elif action == 'remove_moderator':
        await show_moderator_removal_selection(message, state, restaurant_id)

async def show_moderator_removal_selection(message: Message, state: FSMContext, restaurant_id: int):
    """Показать список модераторов для удаления"""
    moderators = await get_restaurant_moderators(restaurant_id)
    
    if not moderators:
        await message.answer("У этого ресторана нет модераторов.")
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    buttons = [[KeyboardButton(text="❌ Отменить")]]
    moderator_mapping = {}  # Словарь для mapping текста кнопки -> chat_id
    
    for mod in moderators:
        username = mod.get('username', '')
        first_name = mod.get('first_name', '')
        last_name = mod.get('last_name', '')
        chat_id = mod.get('chat_id', '')
        
        # Формируем отображаемое имя
        display_name = f"{first_name} {last_name}".strip() if first_name or last_name else f"ID: {chat_id}"
        if username:
            button_text = f"👤 @{username} ({display_name})"
        else:
            button_text = f"👤 {display_name}"
        
        buttons.append([KeyboardButton(text=button_text)])
        # Сохраняем mapping текста кнопки к chat_id
        moderator_mapping[button_text] = chat_id
    
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await state.update_data(selected_restaurant_id=restaurant_id, moderator_mapping=moderator_mapping)
    await message.answer("Выберите модератора для удаления:", reply_markup=markup)
    await state.set_state(BotStates.waiting_moderator_remove_selection)

async def handle_moderator_username(message: Message, state: FSMContext):
    """Обработка ввода username модератора для добавления"""
    if message.text == "❌ Отменить":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    username = message.text.strip()
    if not username.startswith('@'):
        await message.answer('❌ Некорректный формат username. Введите, начиная с "@".')
        return
    
    data = await state.get_data()
    restaurant_id = data.get('selected_restaurant_id')
    
    if not restaurant_id:
        await message.answer("❌ Ошибка: ресторан не выбран.")
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    # Пытаемся получить chat_id: сначала через БД, потом через Telegram API
    bot = message.bot
    chat_id = None
    
    # Сначала пробуем найти в БД по username
    from database.queries import get_chat_id
    db_chat_id = await get_chat_id(username)
    if db_chat_id:
        chat_id = db_chat_id
        logger.info(f"Пользователь {username} найден в БД: chat_id={chat_id}")
    else:
        # Если не найден в БД, пробуем через Telegram API
        chat_id = await get_chat_id_from_username(bot, username)
        if chat_id:
            logger.info(f"Пользователь {username} найден через Telegram API: chat_id={chat_id}")
    
    if not chat_id:
        await message.answer(
            f'❌ Пользователь {username} не найден.\n\n'
            'Возможные причины:\n'
            '• Пользователь не начинал диалог с ботом\n'
            '• Username указан неверно\n'
            '• Профиль пользователя скрыт\n\n'
            'Попробуйте еще раз или убедитесь, что пользователь использовал бота хотя бы раз.'
        )
        return
    
    # Проверяем, существует ли пользователь в таблице users, если нет - добавляем
    try:
        chat_info = await bot.get_chat(chat_id)
        from database.queries import db_manager
        import datetime
        
        # Проверяем, существует ли пользователь
        check_query = '''SELECT chat_id FROM users WHERE chat_id = $1;'''
        existing_user = await db_manager.fetchrow_query(check_query, chat_id)
        
        if not existing_user:
            # Добавляем пользователя в таблицу users
            user_name = f'@{chat_info.username}' if chat_info.username else None
            first_name = chat_info.first_name
            last_name = chat_info.last_name
            date = datetime.datetime.now()
            role = 'user'  # По умолчанию роль 'user', можно будет изменить позже
            status = 'active'
            
            insert_query = '''
                INSERT INTO users (chat_id, first_name, last_name, username, date, role, status) 
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id) DO NOTHING;
            '''
            
            await db_manager.execute_query(
                insert_query, chat_id, first_name, last_name, user_name, date, role, status
            )
            logger.info(f"Пользователь {chat_id} ({username}) добавлен в БД при добавлении как модератор")
    except Exception as e:
        logger.error(f"Ошибка при проверке/добавлении пользователя {chat_id}: {e}")
        # Продолжаем выполнение, даже если не удалось добавить в users
    
    # Проверяем, не является ли пользователь уже модератором этого ресторана
    existing_moderators = await get_restaurant_moderators(restaurant_id)
    for mod in existing_moderators:
        if mod.get('chat_id') == chat_id:
            await message.answer(
                f'❌ Пользователь {username} уже является модератором этого ресторана.'
            )
            markup = get_restaurant_cabinet_keyboard()
            await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
            await state.set_state(BotStates.waiting_restaurant_cabinet)
            return
    
    # Добавляем модератора
    success = await add_user_restaurant(chat_id, restaurant_id)
    
    if success:
        restaurant = await get_restaurant_by_id(restaurant_id)
        restaurant_name = restaurant.get('restaurant_name', 'ресторан') if restaurant else 'ресторан'
        await message.answer(
            f'✅ Пользователь {username} успешно добавлен как модератор ресторана "{restaurant_name}".'
        )
        
        # Отправляем уведомление новому модератору
        try:
            await bot.send_message(
                chat_id,
                f'✅ Вас добавили как модератора ресторана "{restaurant_name}". '
                'Теперь вы можете управлять информацией об этом ресторане.'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления модератору {chat_id}: {e}")
    else:
        await message.answer('❌ Ошибка при добавлении модератора. Попробуйте позже.')
    
    markup = get_restaurant_cabinet_keyboard()
    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
    await state.set_state(BotStates.waiting_restaurant_cabinet)

async def handle_moderator_remove_selection(message: Message, state: FSMContext):
    """Обработка выбора модератора для удаления"""
    if message.text == "❌ Отменить":
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    data = await state.get_data()
    restaurant_id = data.get('selected_restaurant_id')
    moderator_mapping = data.get('moderator_mapping', {})
    
    if not restaurant_id:
        await message.answer("❌ Ошибка: ресторан не выбран.")
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    # Извлекаем chat_id из mapping по тексту кнопки
    button_text = message.text
    selected_chat_id = moderator_mapping.get(button_text)
    
    if not selected_chat_id:
        await message.answer("Модератор не найден. Выберите из предложенных вариантов.")
        return
    
    # Проверяем, что не удаляем самого себя
    if selected_chat_id == message.chat.id:
        await message.answer("❌ Вы не можете удалить самого себя как модератора.")
        markup = get_restaurant_cabinet_keyboard()
        await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
        await state.set_state(BotStates.waiting_restaurant_cabinet)
        return
    
    # Удаляем модератора
    success = await remove_user_restaurant(selected_chat_id, restaurant_id)
    
    if success:
        restaurant = await get_restaurant_by_id(restaurant_id)
        restaurant_name = restaurant.get('restaurant_name', 'ресторан') if restaurant else 'ресторан'
        await message.answer(
            f'✅ Модератор успешно удален из ресторана "{restaurant_name}".'
        )
        
        # Отправляем уведомление удаленному модератору
        try:
            bot = message.bot
            await bot.send_message(
                selected_chat_id,
                f'❌ Вас удалили из модераторов ресторана "{restaurant_name}".'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления модератору {selected_chat_id}: {e}")
    else:
        await message.answer('❌ Ошибка при удалении модератора. Попробуйте позже.')
    
    markup = get_restaurant_cabinet_keyboard()
    await message.answer("🏢 Личный кабинет ресторана", reply_markup=markup)
    await state.set_state(BotStates.waiting_restaurant_cabinet)

def register_restaurant_handlers(dp, bot):
    """Регистрация обработчиков для ресторанов"""
    from aiogram import F
    
    dp.message.register(handle_restaurant_cabinet, StateFilter(BotStates.waiting_restaurant_cabinet))
    dp.message.register(handle_restaurant_selection, StateFilter(BotStates.waiting_restaurant_selection))
    dp.message.register(handle_edit_field_selection, StateFilter(BotStates.waiting_restaurant_edit_field))
    dp.message.register(handle_edit_value_input, StateFilter(BotStates.waiting_restaurant_edit_value))
    dp.message.register(handle_menu_manager_action, StateFilter(BotStates.waiting_restaurant_menu_manager))
    dp.message.register(handle_menu_upload, StateFilter(BotStates.waiting_restaurant_menu_upload))
    dp.message.register(handle_menu_upload, F.document, StateFilter(BotStates.waiting_restaurant_menu_upload))
    dp.message.register(handle_banquet_manager_action, StateFilter(BotStates.waiting_restaurant_banquet_manager))
    dp.message.register(handle_banquet_upload, StateFilter(BotStates.waiting_restaurant_banquet_upload))
    dp.message.register(handle_banquet_upload, F.document, StateFilter(BotStates.waiting_restaurant_banquet_upload))
    dp.message.register(handle_moderator_restaurant_selection, StateFilter(BotStates.waiting_moderator_restaurant_selection))
    dp.message.register(handle_moderator_username, StateFilter(BotStates.waiting_moderator_username))
    dp.message.register(handle_moderator_remove_selection, StateFilter(BotStates.waiting_moderator_remove_selection))
    logger.info("Restaurant handlers зарегистрированы")
