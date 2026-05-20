"""Общие обработчики для всех пользователей"""
from aiogram import F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from database.queries import (
    add_new_user, add_log_users, get_user_role, change_status_sql, get_user_restaurants
)
from utils.keyboards import get_main_menu_keyboard, get_regions_keyboard
from handlers.user import show_regions_or_restaurants
from handlers.ai_assistant import handle_ai_start
import logging

logger = logging.getLogger(__name__)


async def main_menu(message: Message, state: FSMContext):
    """Главное меню в зависимости от роли"""
    await state.clear()
    await add_new_user(message)
    await add_log_users(message)
    role, status = (await get_user_role(message))[0]

    if role == 'banned':
        await message.answer('⛔ Вы забанены')
        return

    if status == 'inactive':
        await change_status_sql('active', message.chat.id)
        await message.answer('💚 Очень рады, что вы вернулись!')

    if role == 'admin':
        admin_restaurants = await get_user_restaurants(message.chat.id)
        has_restaurants = len(
            admin_restaurants) > 0 if admin_restaurants else False
        markup = get_main_menu_keyboard(
            'admin', has_restaurants=has_restaurants)
        await message.answer('Что необходимо сделать?', reply_markup=markup)
        from states.bot_states import BotStates
        await state.set_state(BotStates.waiting_admin_action)
    elif role == 'restaurant':
        markup = get_main_menu_keyboard('restaurant')
        await message.answer('🏢 Личный кабинет ресторана', reply_markup=markup)
        from states.bot_states import BotStates
        await state.set_state(BotStates.waiting_restaurant_cabinet)
    else:
        # Обычный пользователь — показываем меню с кнопкой AI
        from states.bot_states import BotStates
        markup = get_main_menu_keyboard('user')
        await message.answer('🌴 Добро пожаловать в Bali.go!', reply_markup=markup)
        await state.set_state(BotStates.waiting_user_menu)


async def start_handler(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    logger.info(
        f"✅ Обработчик /start вызван для пользователя {message.from_user.id}")
    try:
        await main_menu(message, state)
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


async def main_menu_button_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'Вернуться в главное меню'"""
    logger.info(
        f"✅ Обработчик 'Вернуться в главное меню' вызван для пользователя {message.from_user.id}")
    try:
        await main_menu(message, state)
    except Exception as e:
        logger.error(f"Ошибка в main_menu_button_handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


async def handle_user_menu(message: Message, state: FSMContext):
    if message.text == "🤖 AI-ассистент":
        await handle_ai_start(message, state)
    elif message.text == "🌴 Выбрать район":
        await show_regions_or_restaurants(message, state, is_admin=False)
    elif message.text == "🏠 Вернуться в главное меню":
        await main_menu(message, state)
    else:
        await show_regions_or_restaurants(message, state, is_admin=False)


async def unhandled_message_handler(message: Message, state: FSMContext):
    """Обработчик для необработанных сообщений"""
    logger.warning(
        f"⚠️ Необработанное сообщение от пользователя {message.from_user.id}: {message.text or message.content_type}")
    try:
        await main_menu(message, state)
    except Exception as e:
        logger.error(f"Ошибка в unhandled_message_handler: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка. Возвращаю вас в главное меню...")
            await main_menu(message, state)
        except Exception as e2:
            logger.error(
                f"Критическая ошибка при возврате в главное меню: {e2}", exc_info=True)


def register_common_handlers(dp, bot):
    """Регистрация общих обработчиков"""
    logger.info("Начинаем регистрацию common handlers...")

    try:
        dp.message.register(start_handler, Command("start"))
        logger.info("Обработчик /start зарегистрирован")
    except Exception as e:
        logger.error(f"Ошибка регистрации /start: {e}", exc_info=True)

    try:
        dp.message.register(main_menu_button_handler,
                            F.text == "🏠 Вернуться в главное меню")
        logger.info("Обработчик 'Вернуться в главное меню' зарегистрирован")
    except Exception as e:
        logger.error(f"Ошибка регистрации кнопки: {e}", exc_info=True)

    try:
        dp.message.register(handle_ai_start, F.text == "🤖 AI-ассистент")
        logger.info("Обработчик AI-ассистента зарегистрирован")
    except Exception as e:
        logger.error(f"Ошибка регистрации AI-ассистента: {e}", exc_info=True)

    try:
        from states.bot_states import BotStates
        from aiogram.filters import StateFilter
        dp.message.register(handle_user_menu, StateFilter(
            BotStates.waiting_user_menu))
        logger.info("Обработчик меню пользователя зарегистрирован")
    except Exception as e:
        logger.error(
            f"Ошибка регистрации меню пользователя: {e}", exc_info=True)

    logger.info(
        f"Общие обработчики зарегистрированы. Всего handlers: {len(dp.message.handlers)}")


def register_unhandled_handler(dp, bot):
    """Регистрация обработчика для необработанных сообщений (должен регистрироваться последним)"""
    logger.info("Регистрация обработчика необработанных сообщений...")
    try:
        dp.message.register(unhandled_message_handler)
        logger.info("Обработчик необработанных сообщений зарегистрирован")
    except Exception as e:
        logger.error(
            f"Ошибка регистрации обработчика необработанных сообщений: {e}", exc_info=True)
