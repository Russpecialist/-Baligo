# Добавить в handlers/admin.py в функцию handle_admin_action новый elif:
# elif message.text == "🎉 Управление мероприятиями":
#     await handle_events_bali_menu(message, state)

"""Обработчики управления мероприятиями для админа"""
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from states.bot_states import BotStates
from database.queries import db_manager, get_regions
from utils.keyboards import get_cancel_keyboard, get_regions_keyboard
import logging

logger = logging.getLogger(__name__)


async def handle_events_bali_menu(message: Message, state: FSMContext):
    """Меню управления мероприятиями"""
    buttons = [
        [KeyboardButton(text="➕ Добавить мероприятие")],
        [KeyboardButton(text="🗑 Удалить мероприятие")],
        [KeyboardButton(text="🏠 Вернуться в главное меню")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("🎉 Управление мероприятиями:", reply_markup=markup)
    await state.set_state(BotStates.waiting_events_bali_menu)


async def handle_events_bali_action(message: Message, state: FSMContext):
    """Обработка действий в меню мероприятий"""
    from handlers.common import main_menu

    if message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
        return

    if message.text == "➕ Добавить мероприятие":
        # Выбор района
        regions = await get_regions()
        buttons = [[KeyboardButton(text=r)] for r in regions]
        buttons.append([KeyboardButton(text="❌ Отменить")])
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("Выберите район для мероприятия:", reply_markup=markup)
        await state.set_state(BotStates.waiting_events_bali_region)
        return

    if message.text == "🗑 Удалить мероприятие":
        # Показать список всех мероприятий
        query = "SELECT id, title FROM events_bali WHERE status = 'approved' ORDER BY created_at DESC;"
        rows = await db_manager.fetch_query(query)
        if not rows:
            await message.answer("Нет мероприятий для удаления.")
            await handle_events_bali_menu(message, state)
            return
        buttons = [[KeyboardButton(text=f"{row['id']}. {row['title']}")] for row in rows]
        buttons.append([KeyboardButton(text="❌ Отменить")])
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("Выберите мероприятие для удаления:", reply_markup=markup)
        await state.set_state(BotStates.waiting_events_bali_delete)
        return


async def handle_events_bali_region(message: Message, state: FSMContext):
    """Выбор района для мероприятия"""
    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return

    # Получаем партнёра из района для привязки мероприятия
    query = "SELECT restaurant_id FROM restaurant WHERE region_nm = $1 LIMIT 1;"
    row = await db_manager.fetchrow_query(query, message.text)
    if not row:
        await message.answer("Район не найден. Выберите из списка.")
        return

    await state.update_data(
        events_bali_region=message.text,
        events_bali_restaurant_id=row['restaurant_id']
    )
    await message.answer("Введите название мероприятия:", reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_events_bali_title)


async def handle_events_bali_title(message: Message, state: FSMContext):
    """Ввод названия мероприятия"""
    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return
    await state.update_data(events_bali_title=message.text)
    await message.answer("Введите описание/релиз мероприятия:", reply_markup=get_cancel_keyboard())
    await state.set_state(BotStates.waiting_events_bali_description)


async def handle_events_bali_description(message: Message, state: FSMContext):
    """Ввод описания мероприятия"""
    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return
    await state.update_data(events_bali_description=message.text)
    await message.answer(
        "Введите ссылку на Guest List (или отправьте '-' если нет):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BotStates.waiting_events_bali_url)


async def handle_events_bali_url(message: Message, state: FSMContext):
    """Ввод ссылки на Guest List"""
    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return
    url = message.text.strip() if message.text != '-' else None
    await state.update_data(events_bali_url=url)

    buttons = [
        [KeyboardButton(text="⏭ Пропустить")],
        [KeyboardButton(text="❌ Отменить")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer(
        "Отправьте афишу мероприятия (фото) или нажмите 'Пропустить':",
        reply_markup=markup
    )
    await state.set_state(BotStates.waiting_events_bali_photo)


async def handle_events_bali_photo(message: Message, state: FSMContext):
    """Загрузка фото афиши"""
    from handlers.common import main_menu

    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return

    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    # Если пропустили — photo_file_id остаётся None

    await state.update_data(events_bali_photo=photo_file_id)
    data = await state.get_data()

    # Сохраняем в БД
    try:
        query = """
            INSERT INTO events_bali 
            (restaurant_id, title, description, guest_list_url, photo_file_id, status)
            VALUES ($1, $2, $3, $4, $5, 'approved')
            RETURNING id;
        """
        result = await db_manager.fetchrow_query(
            query,
            data['events_bali_restaurant_id'],
            data['events_bali_title'],
            data.get('events_bali_description'),
            data.get('events_bali_url'),
            photo_file_id
        )
        if result:
            await message.answer(
                f"✅ Мероприятие «{data['events_bali_title']}» добавлено!\n"
                f"Район: {data['events_bali_region']}"
            )
        else:
            await message.answer("❌ Ошибка при сохранении мероприятия.")
    except Exception as e:
        logger.error(f"Ошибка добавления мероприятия: {e}")
        await message.answer("❌ Ошибка при сохранении мероприятия.")

    await main_menu(message, state)


async def handle_events_bali_delete(message: Message, state: FSMContext):
    """Удаление мероприятия"""
    from handlers.common import main_menu

    if message.text == "❌ Отменить":
        await handle_events_bali_menu(message, state)
        return

    try:
        event_id = int(message.text.split('.')[0].strip())
        query = "DELETE FROM events_bali WHERE id = $1 RETURNING title;"
        result = await db_manager.fetchrow_query(query, event_id)
        if result:
            await message.answer(f"✅ Мероприятие «{result['title']}» удалено!")
        else:
            await message.answer("❌ Мероприятие не найдено.")
    except Exception as e:
        logger.error(f"Ошибка удаления мероприятия: {e}")
        await message.answer("❌ Ошибка при удалении.")

    await main_menu(message, state)
