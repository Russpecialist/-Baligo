"""AI-ассистент по Бали на базе GPT-4o с веб-поиском"""
import os
import logging
from openai import AsyncOpenAI
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """Ты — умный AI-ассистент приложения Bali.go, помогающий людям узнать всё о жизни и отдыхе на Бали.

Ты отвечаешь на любые вопросы про Бали:
- Рестораны, кафе, бары
- Отели и виллы
- СПА, бани, массаж
- Спортивные залы и активности
- Достопримечательности и пляжи
- Визы и документы
- Транспорт и логистика
- Погода и лучшее время для поездки
- Районы: Canggu, Ubud, Seminyak, Uluwatu и другие
- Местная культура и традиции
- Цены и бюджет
- Советы туристам и экспатам

Отвечай на русском языке. Будь дружелюбным, конкретным и полезным.
Если вопрос не связан с Бали — вежливо перенаправь разговор на тему Бали.
Используй эмодзи для наглядности. Ответы делай структурированными но не слишком длинными."""


def get_ai_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура в режиме AI-ассистента"""
    buttons = [
        [KeyboardButton(text="🏠 Вернуться в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


async def handle_ai_start(message: Message, state: FSMContext):
    """Вход в режим AI-ассистента"""
    await state.set_state(BotStates.waiting_ai_message)
    await state.update_data(ai_history=[])
    markup = get_ai_keyboard()
    await message.answer(
        "🤖 *AI-ассистент по Бали*\n\n"
        "Привет! Я знаю всё про Бали 🌴\n"
        "Спрашивай про рестораны, отели, пляжи, визы, районы — всё что угодно!\n\n"
        "_Для выхода нажми кнопку ниже_",
        reply_markup=markup,
        parse_mode="Markdown"
    )


async def handle_ai_message(message: Message, state: FSMContext):
    """Обработка сообщений в режиме AI-ассистента"""
    if message.text == "🏠 Вернуться в главное меню":
        from handlers.common import main_menu
        await main_menu(message, state)
        return

    if not OPENAI_API_KEY:
        await message.answer("❌ AI-ассистент временно недоступен. Обратитесь к администратору.")
        return

    # Показываем что печатаем
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Получаем историю диалога
    data = await state.get_data()
    history = data.get("ai_history", [])

    # Добавляем сообщение пользователя
    history.append({"role": "user", "content": message.text})

    # Ограничиваем историю последними 10 сообщениями
    if len(history) > 10:
        history = history[-10:]

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *history
            ],
            max_tokens=1000,
            temperature=0.7
        )

        answer = response.choices[0].message.content

        # Добавляем ответ в историю
        history.append({"role": "assistant", "content": answer})
        await state.update_data(ai_history=history)

        await message.answer(answer, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка OpenAI API: {e}")
        await message.answer(
            "😔 Произошла ошибка при обращении к AI. Попробуй ещё раз или вернись в главное меню."
        )


def register_ai_handlers(dp, bot):
    """Регистрация обработчиков AI-ассистента"""
    dp.message.register(handle_ai_message, StateFilter(
        BotStates.waiting_ai_message))
    logger.info("AI assistant handlers зарегистрированы")
