"""AI-ассистент по Бали на базе Groq (llama-3.3-70b) с веб-поиском"""
import os
import json
import logging
import httpx
from groq import AsyncGroq
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

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

ВАЖНО: Когда пользователь спрашивает про текущую погоду, актуальные события, новости или любую информацию требующую актуальных данных — ВСЕГДА используй инструмент web_search. Не отвечай из памяти на вопросы про "сейчас", "сегодня", "текущий".

Отвечай на русском языке. Будь дружелюбным, конкретным и полезным.
Если вопрос не связан с Бали — вежливо перенаправь разговор на тему Бали.
Используй эмодзи для наглядности. Ответы делай структурированными но не слишком длинными."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Поиск актуальной информации в интернете. Используй для получения текущей погоды, новостей, актуальных событий.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на английском языке"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


async def do_web_search(query: str) -> str:
    """Выполняет веб-поиск через DuckDuckGo"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            data = response.json()

        results = []
        if data.get("AbstractText"):
            results.append(data["AbstractText"])
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(topic["Text"])

        if results:
            return "\n".join(results[:3])
        else:
            return f"По запросу '{query}' актуальных данных не найдено."

    except Exception as e:
        logger.error(f"Ошибка веб-поиска: {e}")
        return f"Не удалось выполнить поиск: {str(e)}"


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

    if not GROQ_API_KEY:
        await message.answer("❌ AI-ассистент временно недоступен. Обратитесь к администратору.")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    data = await state.get_data()
    history = data.get("ai_history", [])
    history.append({"role": "user", "content": message.text})

    if len(history) > 10:
        history = history[-10:]

    try:
        client = AsyncGroq(api_key=GROQ_API_KEY)

        # Первый запрос — модель решает нужен ли поиск
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *history
            ],
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.7
        )

        response_message = response.choices[0].message

        # Если модель решила использовать поиск
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            search_query = json.loads(tool_call.function.arguments)["query"]

            logger.info(f"AI выполняет поиск: {search_query}")
            await message.bot.send_chat_action(message.chat.id, "typing")

            search_result = await do_web_search(search_query)

            # Второй запрос с результатами поиска
            messages_with_search = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *history,
                {"role": "assistant", "content": None,
                    "tool_calls": response_message.tool_calls},
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": search_result
                }
            ]

            final_response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_with_search,
                max_tokens=1000,
                temperature=0.7
            )
            answer = final_response.choices[0].message.content
        else:
            answer = response_message.content

        history.append({"role": "assistant", "content": answer})
        await state.update_data(ai_history=history)

        # Groq может вернуть Markdown — отправляем с parse_mode
        try:
            await message.answer(answer, parse_mode="Markdown")
        except Exception:
            await message.answer(answer)

    except Exception as e:
        logger.error(f"Ошибка Groq API: {e}")
        await message.answer(
            "😔 Произошла ошибка при обращении к AI. Попробуй ещё раз или вернись в главное меню."
        )


def register_ai_handlers(dp, bot):
    """Регистрация обработчиков AI-ассистента"""
    dp.message.register(handle_ai_message, StateFilter(
        BotStates.waiting_ai_message))
    logger.info("AI assistant handlers зарегистрированы")
