"""Обработчики для управления акциями и событиями ресторанов"""
import os
from aiogram import F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from database.queries import (
    get_user_restaurants, get_promotions, get_events,
    get_promotion_by_id, get_event_by_id,
    create_promotion_event_approval, get_all_admin_chat_ids, get_restaurant_by_id,
    get_user_role_by_chat_id, get_all_restaurants
)
from utils.keyboards import (
    get_restaurant_cabinet_keyboard, get_cancel_keyboard,
    get_promotions_list_keyboard, get_promotion_event_edit_keyboard,
    get_skip_photo_keyboard
)
from utils.helpers import log_error, send_approval_notification
from handlers.common import main_menu
from states.bot_states import BotStates
import logging

logger = logging.getLogger(__name__)

# ========== Обработчики для акций ==========

async def handle_promotions_start(message: Message, state: FSMContext):
    """Начало работы с акциями"""
    chat_id = message.chat.id
    role, status = await get_user_role_by_chat_id(chat_id)
    is_admin = (role == 'admin' and status == 'active')
    
    # Если админ, показываем все рестораны; иначе только свои
    if is_admin:
        all_restaurants = await get_all_restaurants()
        restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
    else:
        restaurants = await get_user_restaurants(chat_id)
    
    if not restaurants:
        if is_admin:
            await message.answer("В системе нет ресторанов.")
        else:
            await message.answer("У вас нет привязанных ресторанов.")
        await main_menu(message, state)
        return
    
    # Если один ресторан, сразу показываем список
    if len(restaurants) == 1:
        restaurant_id = restaurants[0]['restaurant_id']
        await show_promotions_list(message, state, restaurant_id)
    else:
        # Показываем выбор ресторана
        buttons = [[KeyboardButton(text="❌ Отменить")]]
        for r in restaurants:
            buttons.append([KeyboardButton(text=r['restaurant_name'])])
        
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("Выберите ресторан для управления акциями:", reply_markup=markup)
        await state.update_data(action='promotions')
        await state.set_state(BotStates.waiting_restaurant_selection)

async def show_promotions_list(message: Message, state: FSMContext, restaurant_id: int, page: int = 0):
    """Показать список акций с пагинацией"""
    promotions = await get_promotions(restaurant_id, status='approved')
    
    await state.update_data(
        selected_restaurant_id=restaurant_id,
        promotions_page=page
    )
    
    if not promotions:
        text = "📋 Список акций пуст.\n\nИспользуйте кнопку ниже, чтобы добавить новую акцию."
    else:
        text = f"📋 Акции ресторана (страница {page + 1}):\n\n"
        start_idx = page * 5
        end_idx = min(start_idx + 5, len(promotions))
        for i in range(start_idx, end_idx):
            promo = promotions[i]
            text += f"{i+1}. {promo['title']}\n"
    
    markup = get_promotions_list_keyboard(promotions, page, item_type='promotion')
    await message.answer(text, reply_markup=markup)
    await state.set_state(BotStates.waiting_promotions_list)

async def handle_promotions_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка callback для акций"""
    data = callback.data
    data_parts = data.split('_')
    
    if data == 'promotion_back':
        await callback.message.delete()
        await main_menu(callback.message, state)
        return
    
    if data == 'promotion_new':
        # Создание новой акции
        await callback.message.delete()
        await callback.message.answer(
            "Введите название акции:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(BotStates.waiting_promotion_title)
        await callback.answer()
        return
    
    if data.startswith('promotion_page_'):
        # Пагинация
        page = int(data_parts[2])
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        if restaurant_id:
            await callback.message.delete()
            await show_promotions_list(callback.message, state, restaurant_id, page)
        await callback.answer()
        return
    
    if data.startswith('promotion_edit_'):
        # Редактирование акции
        promotion_id = int(data_parts[2])
        promotion = await get_promotion_by_id(promotion_id)
        if not promotion:
            await callback.answer("Акция не найдена", show_alert=True)
            return
        
        text = f"📋 Акция: {promotion['title']}\n\n"
        if promotion['description']:
            text += f"Описание: {promotion['description']}\n"
        
        if promotion['photo_file_id']:
            await callback.message.delete()
            await callback.message.answer_photo(
                promotion['photo_file_id'],
                caption=text,
                reply_markup=get_promotion_event_edit_keyboard(promotion_id, 'promotion')
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=get_promotion_event_edit_keyboard(promotion_id, 'promotion')
            )
        await callback.answer()
        return
    
    if data.startswith('promotion_delete_'):
        # Удаление акции
        promotion_id = int(data_parts[2])
        promotion = await get_promotion_by_id(promotion_id)
        if not promotion:
            await callback.answer("Акция не найдена", show_alert=True)
            return
        
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        
        # Создаем запрос на согласование удаления
        import json
        old_data = {
            'id': promotion['id'],
            'title': promotion['title'],
            'description': promotion['description'],
            'photo_file_id': promotion.get('photo_file_id')
        }
        
        approval_id = await create_promotion_event_approval(
            restaurant_id=restaurant_id,
            type='promotion',
            action='delete',
            requested_by=callback.from_user.id,
            item_id=promotion_id,
            old_data=old_data
        )
        
        if approval_id:
            await callback.answer("Запрос на удаление отправлен на согласование")
            # Уведомляем админов
            admin_chat_ids = await get_all_admin_chat_ids()
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                await send_approval_notification(
                    callback.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
                )
            
            # Обновляем список
            await callback.message.delete()
            await show_promotions_list(callback.message, state, restaurant_id, 0)
        else:
            await callback.answer("Ошибка при создании запроса", show_alert=True)
        return
    
    await callback.answer()

# ========== Обработчики для событий ==========

async def handle_events_start(message: Message, state: FSMContext):
    """Начало работы с событиями"""
    chat_id = message.chat.id
    role, status = await get_user_role_by_chat_id(chat_id)
    is_admin = (role == 'admin' and status == 'active')
    
    # Если админ, показываем все рестораны; иначе только свои
    if is_admin:
        all_restaurants = await get_all_restaurants()
        restaurants = [{'restaurant_id': r['restaurant_id'], 'restaurant_name': r['restaurant_name']} for r in all_restaurants]
    else:
        restaurants = await get_user_restaurants(chat_id)
    
    if not restaurants:
        if is_admin:
            await message.answer("В системе нет ресторанов.")
        else:
            await message.answer("У вас нет привязанных ресторанов.")
        await main_menu(message, state)
        return
    
    # Если один ресторан, сразу показываем список
    if len(restaurants) == 1:
        restaurant_id = restaurants[0]['restaurant_id']
        await show_events_list(message, state, restaurant_id)
    else:
        # Показываем выбор ресторана
        buttons = [[KeyboardButton(text="❌ Отменить")]]
        for r in restaurants:
            buttons.append([KeyboardButton(text=r['restaurant_name'])])
        
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("Выберите ресторан для управления событиями:", reply_markup=markup)
        await state.update_data(action='events')
        await state.set_state(BotStates.waiting_restaurant_selection)

async def show_events_list(message: Message, state: FSMContext, restaurant_id: int, page: int = 0):
    """Показать список событий с пагинацией"""
    events = await get_events(restaurant_id, status='approved')
    
    await state.update_data(
        selected_restaurant_id=restaurant_id,
        events_page=page
    )
    
    if not events:
        text = "📋 Список событий пуст.\n\nИспользуйте кнопку ниже, чтобы добавить новое событие."
    else:
        text = f"📋 События ресторана (страница {page + 1}):\n\n"
        start_idx = page * 5
        end_idx = min(start_idx + 5, len(events))
        for i in range(start_idx, end_idx):
            event = events[i]
            text += f"{i+1}. {event['title']}\n"
    
    markup = get_promotions_list_keyboard(events, page, item_type='event')
    await message.answer(text, reply_markup=markup)
    await state.set_state(BotStates.waiting_events_list)

async def handle_events_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка callback для событий"""
    data = callback.data
    data_parts = data.split('_')
    
    if data == 'event_back':
        await callback.message.delete()
        await main_menu(callback.message, state)
        return
    
    if data == 'event_new':
        # Создание нового события
        await callback.message.delete()
        await callback.message.answer(
            "Введите название события:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(BotStates.waiting_event_title)
        await callback.answer()
        return
    
    if data.startswith('event_page_'):
        # Пагинация
        page = int(data_parts[2])
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        if restaurant_id:
            await callback.message.delete()
            await show_events_list(callback.message, state, restaurant_id, page)
        await callback.answer()
        return
    
    if data.startswith('event_edit_'):
        # Редактирование события
        event_id = int(data_parts[2])
        event = await get_event_by_id(event_id)
        if not event:
            await callback.answer("Событие не найдено", show_alert=True)
            return
        
        text = f"📋 Событие: {event['title']}\n\n"
        if event['description']:
            text += f"Описание: {event['description']}\n"
        
        if event['photo_file_id']:
            await callback.message.delete()
            await callback.message.answer_photo(
                event['photo_file_id'],
                caption=text,
                reply_markup=get_promotion_event_edit_keyboard(event_id, 'event')
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=get_promotion_event_edit_keyboard(event_id, 'event')
            )
        await callback.answer()
        return
    
    if data.startswith('event_delete_'):
        # Удаление события
        event_id = int(data_parts[2])
        event = await get_event_by_id(event_id)
        if not event:
            await callback.answer("Событие не найдено", show_alert=True)
            return
        
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        
        # Создаем запрос на согласование удаления
        import json
        old_data = {
            'id': event['id'],
            'title': event['title'],
            'description': event['description'],
            'photo_file_id': event.get('photo_file_id')
        }
        
        approval_id = await create_promotion_event_approval(
            restaurant_id=restaurant_id,
            type='event',
            action='delete',
            requested_by=callback.from_user.id,
            item_id=event_id,
            old_data=old_data
        )
        
        if approval_id:
            await callback.answer("Запрос на удаление отправлен на согласование")
            # Уведомляем админов
            admin_chat_ids = await get_all_admin_chat_ids()
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                await send_approval_notification(
                    callback.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
                )
            
            # Обновляем список
            await callback.message.delete()
            await show_events_list(callback.message, state, restaurant_id, 0)
        else:
            await callback.answer("Ошибка при создании запроса", show_alert=True)
        return
    
    await callback.answer()

# ========== Обработчики создания акций ==========

async def handle_promotion_title(message: Message, state: FSMContext):
    """Обработка ввода названия акции"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите название акции:")
        return
    
    await state.update_data(promotion_title=title)
    await message.answer(
        "Введите описание акции:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BotStates.waiting_promotion_description)

async def handle_promotion_description(message: Message, state: FSMContext):
    """Обработка ввода описания акции"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    # Если отправлено фото с подписью, используем подпись как описание
    if message.photo and message.caption:
        description = message.caption.strip()
        photo_file_id = message.photo[-1].file_id
        await state.update_data(promotion_description=description, promotion_photo_file_id=photo_file_id)
        # Переходим к завершению создания акции
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        title = state_data.get('promotion_title')
        
        if not restaurant_id:
            await message.answer("Ошибка: ресторан не выбран.")
            await main_menu(message, state)
            return
        
        # Создаем запрос на согласование
        approval_id = await create_promotion_event_approval(
            restaurant_id=restaurant_id,
            type='promotion',
            action='create',
            requested_by=message.chat.id,
            title=title,
            description=description,
            photo_file_id=photo_file_id
        )
        
        if approval_id:
            await message.answer(
                "✅ Акция создана и отправлена на согласование администратору.\n"
                "Вы получите уведомление после рассмотрения заявки."
            )
            # Уведомляем админов
            admin_chat_ids = await get_all_admin_chat_ids()
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                await send_approval_notification(
                    message.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
                )
        else:
            await message.answer("❌ Ошибка при создании акции. Попробуйте позже.")
        
        await main_menu(message, state)
        return
    
    # Обычный текст
    description = (message.text or message.caption or "").strip()
    if not description:
        await message.answer("Описание не может быть пустым. Введите описание акции:")
        return
    
    await state.update_data(promotion_description=description)
    await message.answer(
        "Отправьте фото для акции (или нажмите 'Пропустить', чтобы продолжить без фото):",
        reply_markup=get_skip_photo_keyboard()
    )
    await state.set_state(BotStates.waiting_promotion_photo)

async def handle_promotion_photo(message: Message, state: FSMContext):
    """Обработка загрузки фото акции"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    photo_file_id = None
    
    if message.text == "⏭ Пропустить":
        # Пропускаем загрузку фото
        photo_file_id = None
    elif message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() in ["пропустить", "skip", "без фото"]:
        # Поддержка текстовых команд для пропуска
        photo_file_id = None
    else:
        # Если не фото и не команда пропустить, просим отправить фото или пропустить
        await message.answer(
            "Отправьте фото для акции или нажмите 'Пропустить', чтобы продолжить без фото:",
            reply_markup=get_skip_photo_keyboard()
        )
        return
    
    state_data = await state.get_data()
    restaurant_id = state_data.get('selected_restaurant_id')
    title = state_data.get('promotion_title')
    description = state_data.get('promotion_description')
    
    if not restaurant_id:
        await message.answer("Ошибка: ресторан не выбран.")
        await main_menu(message, state)
        return
    
    # Создаем запрос на согласование
    approval_id = await create_promotion_event_approval(
        restaurant_id=restaurant_id,
        type='promotion',
        action='create',
        requested_by=message.chat.id,
        title=title,
        description=description,
        photo_file_id=photo_file_id
    )
    
    if approval_id:
        await message.answer(
            "✅ Акция создана и отправлена на согласование администратору.\n"
            "Вы получите уведомление после рассмотрения заявки."
        )
        # Уведомляем админов
        admin_chat_ids = await get_all_admin_chat_ids()
        from database.queries import get_restaurant_by_id
        restaurant = await get_restaurant_by_id(restaurant_id)
        if restaurant:
            await send_approval_notification(
                message.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
            )
    else:
        await message.answer("❌ Ошибка при создании акции. Попробуйте позже.")
    
    await main_menu(message, state)

# ========== Обработчики создания событий ==========

async def handle_event_title(message: Message, state: FSMContext):
    """Обработка ввода названия события"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите название события:")
        return
    
    await state.update_data(event_title=title)
    await message.answer(
        "Введите описание события:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BotStates.waiting_event_description)

async def handle_event_description(message: Message, state: FSMContext):
    """Обработка ввода описания события"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    # Если отправлено фото с подписью, используем подпись как описание
    if message.photo and message.caption:
        description = message.caption.strip()
        photo_file_id = message.photo[-1].file_id
        await state.update_data(event_description=description, event_photo_file_id=photo_file_id)
        # Переходим к завершению создания события
        state_data = await state.get_data()
        restaurant_id = state_data.get('selected_restaurant_id')
        title = state_data.get('event_title')
        
        if not restaurant_id:
            await message.answer("Ошибка: ресторан не выбран.")
            await main_menu(message, state)
            return
        
        # Создаем запрос на согласование
        approval_id = await create_promotion_event_approval(
            restaurant_id=restaurant_id,
            type='event',
            action='create',
            requested_by=message.chat.id,
            title=title,
            description=description,
            photo_file_id=photo_file_id
        )
        
        if approval_id:
            await message.answer(
                "✅ Событие создано и отправлено на согласование администратору.\n"
                "Вы получите уведомление после рассмотрения заявки."
            )
            # Уведомляем админов
            admin_chat_ids = await get_all_admin_chat_ids()
            restaurant = await get_restaurant_by_id(restaurant_id)
            if restaurant:
                await send_approval_notification(
                    message.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
                )
        else:
            await message.answer("❌ Ошибка при создании события. Попробуйте позже.")
        
        await main_menu(message, state)
        return
    
    # Обычный текст
    description = (message.text or message.caption or "").strip()
    if not description:
        await message.answer("Описание не может быть пустым. Введите описание события:")
        return
    
    await state.update_data(event_description=description)
    await message.answer(
        "Отправьте фото для события (или нажмите 'Пропустить', чтобы продолжить без фото):",
        reply_markup=get_skip_photo_keyboard()
    )
    await state.set_state(BotStates.waiting_event_photo)

async def handle_event_photo(message: Message, state: FSMContext):
    """Обработка загрузки фото события"""
    if message.text == "❌ Отменить":
        await main_menu(message, state)
        return
    
    photo_file_id = None
    
    if message.text == "⏭ Пропустить":
        # Пропускаем загрузку фото
        photo_file_id = None
    elif message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() in ["пропустить", "skip", "без фото"]:
        # Поддержка текстовых команд для пропуска
        photo_file_id = None
    else:
        # Если не фото и не команда пропустить, просим отправить фото или пропустить
        await message.answer(
            "Отправьте фото для события или нажмите 'Пропустить', чтобы продолжить без фото:",
            reply_markup=get_skip_photo_keyboard()
        )
        return
    
    state_data = await state.get_data()
    restaurant_id = state_data.get('selected_restaurant_id')
    title = state_data.get('event_title')
    description = state_data.get('event_description')
    
    if not restaurant_id:
        await message.answer("Ошибка: ресторан не выбран.")
        await main_menu(message, state)
        return
    
    # Создаем запрос на согласование
    approval_id = await create_promotion_event_approval(
        restaurant_id=restaurant_id,
        type='event',
        action='create',
        requested_by=message.chat.id,
        title=title,
        description=description,
        photo_file_id=photo_file_id
    )
    
    if approval_id:
        await message.answer(
            "✅ Событие создано и отправлено на согласование администратору.\n"
            "Вы получите уведомление после рассмотрения заявки."
        )
        # Уведомляем админов
        admin_chat_ids = await get_all_admin_chat_ids()
        from database.queries import get_restaurant_by_id
        restaurant = await get_restaurant_by_id(restaurant_id)
        if restaurant:
            await send_approval_notification(
                message.bot, admin_chat_ids, restaurant.get('restaurant_name', 'Ресторан')
            )
    else:
        await message.answer("❌ Ошибка при создании события. Попробуйте позже.")
    
    await main_menu(message, state)

def register_promotions_events_handlers(dp, bot):
    """Регистрация обработчиков для акций и событий"""
    # Обработчики для акций (обработка кнопки "🎁 Изменить Акции" происходит в handle_restaurant_cabinet)
    dp.message.register(handle_promotions_start, StateFilter(BotStates.waiting_promotions_list))
    dp.callback_query.register(handle_promotions_callback, F.data.startswith("promotion_"))
    
    # Обработчики для событий (обработка кнопки "🎊 Изменить События" происходит в handle_restaurant_cabinet)
    dp.message.register(handle_events_start, StateFilter(BotStates.waiting_events_list))
    dp.callback_query.register(handle_events_callback, F.data.startswith("event_"))
    
    # Обработчики создания акций
    dp.message.register(handle_promotion_title, StateFilter(BotStates.waiting_promotion_title))
    # Обработка описания: текст или фото с подписью
    dp.message.register(handle_promotion_description, StateFilter(BotStates.waiting_promotion_description))
    dp.message.register(handle_promotion_photo, StateFilter(BotStates.waiting_promotion_photo))
    dp.message.register(handle_promotion_photo, F.photo, StateFilter(BotStates.waiting_promotion_photo))
    
    # Обработчики создания событий
    dp.message.register(handle_event_title, StateFilter(BotStates.waiting_event_title))
    # Обработка описания: текст или фото с подписью
    dp.message.register(handle_event_description, StateFilter(BotStates.waiting_event_description))
    dp.message.register(handle_event_photo, StateFilter(BotStates.waiting_event_photo))
    dp.message.register(handle_event_photo, F.photo, StateFilter(BotStates.waiting_event_photo))
    
    logger.info("Promotions and events handlers зарегистрированы")
