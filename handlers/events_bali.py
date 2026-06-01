"""Обработчики для мероприятий Bali (просмотр пользователями)"""
import asyncio
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from states.bot_states import BotStates
from database.queries import db_manager
import logging

logger = logging.getLogger(__name__)


async def get_events_bali_by_region(region_nm: str) -> list:
    """Получение мероприятий по району"""
    try:
        query = """
            SELECT e.id, e.title, e.description, e.guest_list_url, 
                   e.photo_file_id, e.pdf_file_id, e.status, e.created_at
            FROM events_bali e
            JOIN restaurant r ON e.restaurant_id = r.restaurant_id
            WHERE r.region_nm = $1 AND e.status = 'approved'
            ORDER BY e.created_at DESC;
        """
        result = await db_manager.fetch_query(query, region_nm)
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(f"Ошибка получения мероприятий для региона {region_nm}: {e}")
        return []


async def show_events_bali_list(message: Message, state: FSMContext):
    """Показать список мероприятий"""
    data = await state.get_data()
    region_nm = data.get('selected_region', '')

    events = await get_events_bali_by_region(region_nm)

    if not events:
        await message.answer(
            "🎉 В этом районе пока нет мероприятий.\nСледите за обновлениями!",
        )
        return

    await state.update_data(events_bali_list=events, events_bali_index=0)
    await show_event_card(message, state, events, 0)
    await state.set_state(BotStates.viewing_events_bali)


async def show_event_card(message: Message, state: FSMContext, events: list, index: int):
    """Показать карточку мероприятия"""
    if not events or index < 0 or index >= len(events):
        return

    event = events[index]

    text = f"🎉 *{event['title']}*\n\n"
    if event.get('description'):
        text += f"{event['description']}\n\n"
    text += f"_{index + 1} из {len(events)}_"

    # Кнопки навигации + Guest List
    buttons = []

    # Кнопка Guest List если есть ссылка
    if event.get('guest_list_url'):
        buttons.append([InlineKeyboardButton(
            text="👥 Guest List",
            url=event['guest_list_url']
        )])

    # Навигация
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"evbali_prev_{index}"
        ))
    if index < len(events) - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️", callback_data=f"evbali_next_{index}"
        ))
    if nav_buttons:
        buttons.append(nav_buttons)

    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    # Если есть PDF афиша — отправляем как фото
    if event.get('photo_file_id'):
        try:
            await message.answer_photo(
                event['photo_file_id'],
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return
        except Exception as e:
            logger.error(f"Ошибка отправки фото мероприятия: {e}")

    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


async def handle_events_bali_navigation(callback: CallbackQuery, state: FSMContext):
    """Навигация по мероприятиям"""
    data_parts = callback.data.split('_')
    action = data_parts[1]  # prev или next
    current_index = int(data_parts[2])

    state_data = await state.get_data()
    events = state_data.get('events_bali_list', [])

    if action == 'next':
        new_index = current_index + 1
    else:
        new_index = current_index - 1

    if new_index < 0 or new_index >= len(events):
        await callback.answer()
        return

    await state.update_data(events_bali_index=new_index)
    event = events[new_index]

    text = f"🎉 *{event['title']}*\n\n"
    if event.get('description'):
        text += f"{event['description']}\n\n"
    text += f"_{new_index + 1} из {len(events)}_"

    buttons = []
    if event.get('guest_list_url'):
        buttons.append([InlineKeyboardButton(
            text="👥 Guest List",
            url=event['guest_list_url']
        )])

    nav_buttons = []
    if new_index > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"evbali_prev_{new_index}"
        ))
    if new_index < len(events) - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️", callback_data=f"evbali_next_{new_index}"
        ))
    if nav_buttons:
        buttons.append(nav_buttons)

    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    try:
        if event.get('photo_file_id') and callback.message.photo:
            from aiogram.types import InputMediaPhoto
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=event['photo_file_id'],
                    caption=text,
                    parse_mode="Markdown"
                ),
                reply_markup=markup
            )
        elif event.get('photo_file_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                event['photo_file_id'],
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка навигации по мероприятиям: {e}")

    await callback.answer()


def register_events_bali_handlers(dp, bot):
    """Регистрация обработчиков мероприятий"""
    dp.callback_query.register(
        handle_events_bali_navigation,
        lambda c: c.data.startswith("evbali_")
    )
    logger.info("Events Bali handlers зарегистрированы")
