"""Обработчики для обычных пользователей (просмотр ресторанов)"""
import asyncio
import os
from aiogram import F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from config import MENU_PATH
from database.queries import (
    get_regions, get_restaurants_by_region, get_banquet_restaurants_by_region,
    get_restaurant_info, get_banquet_restaurants, get_user_role,
    get_promotions, get_events, get_restaurant_id_by_name,
    get_categories_in_region, get_restaurants_by_region_and_category,
    CATEGORIES, CATEGORY_LABEL_TO_DB
)
from utils.keyboards import (
    get_regions_keyboard, get_categories_keyboard, get_restaurants_keyboard,
    get_restaurant_info_keyboard, get_promotion_event_view_keyboard
)
from utils.helpers import log_error, split_text_for_caption, split_text_into_messages
from utils.pdf_converter import pdf_to_images, load_telegram_file_ids, save_telegram_file_ids
from states.bot_states import BotStates
import logging

logger = logging.getLogger(__name__)


async def send_photos_as_media_group(message: Message, photos: list, captions: list = None, file_ids: dict = None):
    """
    Отправляет несколько фото одной группой (media group)
    Telegram позволяет до 10 фото в одной группе

    Args:
        message: Объект сообщения для отправки
        photos: Список путей к изображениям или FSInputFile
        captions: Список подписей для каждого фото (опционально)
        file_ids: Словарь {page_num: file_id} для использования кэша

    Returns:
        list: Список отправленных сообщений
    """
    from utils.helpers import split_text_for_caption

    if not photos:
        return []

    # Максимум 10 фото в одной группе
    MAX_PHOTOS_PER_GROUP = 10
    all_sent_messages = []
    temp_files = []  # Список временных файлов для удаления

    # Разбиваем на группы по 10 фото
    for group_start in range(0, len(photos), MAX_PHOTOS_PER_GROUP):
        group_end = min(group_start + MAX_PHOTOS_PER_GROUP, len(photos))
        group_photos = photos[group_start:group_end]
        group_captions = captions[group_start:group_end] if captions else [
            None] * len(group_photos)

        media_group = []
        for i, photo_path in enumerate(group_photos):
            page_num = group_start + i + 1
            caption = group_captions[i] if i < len(group_captions) else None

            # Разбиваем подпись, если она слишком длинная
            if caption:
                caption_text, _ = split_text_for_caption(
                    caption, max_length=1024)
            else:
                caption_text = None

            # Используем file_id, если есть
            if file_ids and page_num in file_ids:
                media_item = InputMediaPhoto(
                    media=file_ids[page_num], caption=caption_text)
            else:
                # Используем файл
                if isinstance(photo_path, str):
                    # Проверяем размер файла и уменьшаем, если нужно
                    try:
                        from PIL import Image
                        img = Image.open(photo_path)
                        # Если изображение слишком большое, уменьшаем его
                        if img.width > 2000 or img.height > 2000:
                            img.thumbnail(
                                (2000, 2000), Image.Resampling.LANCZOS)
                            import tempfile
                            temp_file = tempfile.NamedTemporaryFile(
                                delete=False, suffix='.png')
                            img.save(temp_file.name, 'PNG',
                                     optimize=True, quality=85)
                            temp_file.close()
                            photo_file = FSInputFile(temp_file.name)
                            # Сохраняем путь к временному файлу для последующего удаления
                            temp_files.append(temp_file.name)
                        else:
                            photo_file = FSInputFile(photo_path)
                    except Exception as e:
                        logger.warning(
                            f"Не удалось обработать изображение {photo_path}, используем как есть: {e}")
                        photo_file = FSInputFile(photo_path)
                else:
                    photo_file = photo_path
                media_item = InputMediaPhoto(
                    media=photo_file, caption=caption_text)

            media_group.append(media_item)

        # Отправляем группу с повторными попытками и увеличенным таймаутом
        max_retries = 3
        retry_delay = 2.0
        sent_messages = None

        for attempt in range(max_retries):
            try:
                # Используем bot.send_media_group с увеличенным таймаутом
                sent_messages = await message.bot.send_media_group(
                    chat_id=message.chat.id,
                    media=media_group,
                    request_timeout=120.0  # 120 секунд таймаут для больших файлов
                )
                all_sent_messages.extend(sent_messages)

                # Сохраняем file_id из ответа
                if file_ids is not None:
                    for i, sent_msg in enumerate(sent_messages):
                        if sent_msg.photo:
                            page_num = group_start + i + 1
                            file_ids[page_num] = sent_msg.photo[-1].file_id

                # Удаляем временные файлы, если они были созданы
                for temp_file in temp_files:
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                temp_files.clear()

                # Успешно отправлено, выходим из цикла повторов
                break

            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Таймаут при отправке media group (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # Увеличиваем задержку с каждой попыткой
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"Не удалось отправить media group после {max_retries} попыток")
                    sent_messages = None
            except ConnectionResetError as e:
                logger.warning(
                    f"Соединение разорвано при отправке media group (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"Не удалось отправить media group после {max_retries} попыток")
                    sent_messages = None
            except Exception as e:
                error_str = str(e)
                if "timeout" in error_str.lower() or "Request timeout" in error_str:
                    logger.warning(
                        f"Таймаут при отправке media group (попытка {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                    else:
                        logger.error(
                            f"Не удалось отправить media group после {max_retries} попыток")
                        sent_messages = None
                else:
                    # Другие ошибки - не повторяем
                    logger.error(f"Ошибка отправки media group: {e}")
                    sent_messages = None
                    break

        # Если группа успешно отправлена
        if sent_messages:
            # Небольшая задержка между группами
            if group_end < len(photos):
                await asyncio.sleep(0.5)
        else:
            # Если не удалось отправить группой, отправляем по одному
            logger.info("Переходим на отправку по одному изображению")
            # Удаляем временные файлы, если они были созданы
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            temp_files.clear()

            # Отправляем по одному изображению с повторными попытками
            for i, photo_path in enumerate(group_photos):
                page_num = group_start + i + 1
                caption = group_captions[i] if i < len(
                    group_captions) else None

                photo_sent = False
                for attempt in range(max_retries):
                    try:
                        if file_ids and page_num in file_ids:
                            sent_msg = await message.bot.send_photo(
                                chat_id=message.chat.id,
                                photo=file_ids[page_num],
                                caption=caption,
                                request_timeout=120.0
                            )
                        else:
                            if isinstance(photo_path, str):
                                photo_file = FSInputFile(photo_path)
                            else:
                                photo_file = photo_path
                            sent_msg = await message.bot.send_photo(
                                chat_id=message.chat.id,
                                photo=photo_file,
                                caption=caption,
                                request_timeout=120.0
                            )

                        all_sent_messages.append(sent_msg)

                        # Сохраняем file_id
                        if sent_msg.photo and file_ids is not None:
                            file_ids[page_num] = sent_msg.photo[-1].file_id

                        photo_sent = True
                        await asyncio.sleep(0.3)
                        break  # Успешно отправлено, выходим из цикла повторов

                    except (asyncio.TimeoutError, ConnectionResetError) as e2:
                        logger.warning(
                            f"Таймаут/разрыв соединения при отправке фото {page_num} (попытка {attempt + 1}/{max_retries}): {e2}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                        else:
                            logger.error(
                                f"Не удалось отправить фото {page_num} после {max_retries} попыток")
                    except Exception as e2:
                        error_str = str(e2)
                        if "timeout" in error_str.lower() or "Request timeout" in error_str:
                            logger.warning(
                                f"Таймаут при отправке фото {page_num} (попытка {attempt + 1}/{max_retries}): {e2}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay * (attempt + 1))
                            else:
                                logger.error(
                                    f"Не удалось отправить фото {page_num} после {max_retries} попыток")
                        else:
                            # Другие ошибки - не повторяем, сразу переходим к обработке
                            break

                if not photo_sent:
                    # Если не удалось отправить обычным способом, пробуем уменьшить размер
                    logger.warning(
                        f"Попытка уменьшить размер изображения {page_num} для отправки")
                    try:
                        from PIL import Image
                        import tempfile
                        # Открываем изображение и уменьшаем его
                        if isinstance(photo_path, str):
                            img_path = photo_path
                        else:
                            img_path = photo_path.path if hasattr(
                                photo_path, 'path') else str(photo_path)
                        img = Image.open(img_path)
                        # Уменьшаем до максимум 2000x2000
                        img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                        # Сохраняем во временный файл
                        temp_file = tempfile.NamedTemporaryFile(
                            delete=False, suffix='.png')
                        img.save(temp_file.name, 'PNG',
                                 optimize=True, quality=85)
                        temp_file.close()
                        # Отправляем уменьшенное изображение с таймаутом
                        try:
                            sent_msg = await message.bot.send_photo(
                                chat_id=message.chat.id,
                                photo=FSInputFile(temp_file.name),
                                caption=caption,
                                request_timeout=120.0
                            )
                            all_sent_messages.append(sent_msg)
                            # Сохраняем file_id
                            if sent_msg.photo and file_ids is not None:
                                file_ids[page_num] = sent_msg.photo[-1].file_id
                        finally:
                            # Удаляем временный файл
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                    except Exception as e3:
                        logger.error(
                            f"Не удалось отправить уменьшенное изображение {page_num}: {e3}")

    return all_sent_messages


async def send_photo_with_caption(message: Message, photo_or_file_id, caption: str = ""):
    """
    Отправляет фото с подписью, разбивая длинную подпись на несколько сообщений

    Args:
        message: Объект сообщения для отправки
        photo_or_file_id: FSInputFile или file_id фото
        caption: Подпись к фото (может быть длинной)
    """
    from utils.helpers import split_text_for_caption

    # Разбиваем подпись, если она слишком длинная
    caption_text, remaining_text = split_text_for_caption(
        caption, max_length=1024)

    # Отправляем фото с подписью
    try:
        if isinstance(photo_or_file_id, str):
            # Это file_id
            sent_message = await message.answer_photo(photo_or_file_id, caption=caption_text if caption_text else None)
        else:
            # Это FSInputFile
            sent_message = await message.answer_photo(photo_or_file_id, caption=caption_text if caption_text else None)
    except Exception as e:
        # Обработка ошибки IMAGE_PROCESS_FAILED
        if "IMAGE_PROCESS_FAILED" in str(e) or "Bad Request" in str(e):
            logger.warning(
                f"Ошибка обработки изображения, пытаемся уменьшить размер: {e}")
            # Если это FSInputFile, попробуем уменьшить размер изображения
            if not isinstance(photo_or_file_id, str):
                try:
                    from PIL import Image
                    import tempfile
                    # Открываем изображение и уменьшаем его
                    img_path = photo_or_file_id.path if hasattr(
                        photo_or_file_id, 'path') else str(photo_or_file_id)
                    img = Image.open(img_path)
                    # Уменьшаем до максимум 2000x2000
                    img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                    # Сохраняем во временный файл
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix='.png')
                    img.save(temp_file.name, 'PNG', optimize=True, quality=85)
                    temp_file.close()
                    # Отправляем уменьшенное изображение
                    sent_message = await message.answer_photo(FSInputFile(temp_file.name), caption=caption_text if caption_text else None)
                    # Удаляем временный файл
                    os.unlink(temp_file.name)
                except Exception as e2:
                    logger.error(
                        f"Не удалось отправить уменьшенное изображение: {e2}")
                    raise e
            else:
                raise e
        else:
            raise e

    # Если есть остаток текста, отправляем его отдельными сообщениями
    if remaining_text:
        text_parts = split_text_into_messages(remaining_text, max_length=4096)
        for part in text_parts:
            await message.answer(part)
            await asyncio.sleep(0.1)

    return sent_message


async def show_regions_or_restaurants(message: Message, state: FSMContext, is_admin: bool = False):
    """Показать районы Бали (или сразу категории, если район один)"""
    regions = await get_regions()

    if len(regions) == 0:
        await message.answer("Нет доступных районов. Обратитесь к администратору.")
        return

    if len(regions) == 1:
        await show_region_categories(message, state, regions[0], is_admin)
    else:
        markup = get_regions_keyboard(regions, is_admin)
        await message.answer('🌴 Выберите район Бали:', reply_markup=markup)
        await state.set_state(BotStates.waiting_region)


async def show_region_categories(message: Message, state: FSMContext, region_name: str, is_admin: bool = False):
    """Показать категории партнёров выбранного района"""
    categories = await get_categories_in_region(region_name)
    if not categories:
        await message.answer(f"В районе {region_name} пока нет партнёров.")
        return

    markup = get_categories_keyboard(categories)
    await message.answer(
        f"📍 Район: <b>{region_name}</b>\n\nВыберите категорию:",
        reply_markup=markup,
        parse_mode="HTML"
    )
    await state.update_data(selected_region=region_name, is_admin=is_admin)
    await state.set_state(BotStates.waiting_category)


async def show_region_restaurants(message: Message, state: FSMContext, region_name: str, is_admin: bool = False):
    """Показать список партнёров выбранного района (все категории — для совместимости)"""
    await show_region_categories(message, state, region_name, is_admin)


async def show_category_partners(message: Message, state: FSMContext, region_name: str, category_label: str):
    """Показать список партнёров по категории"""
    category_db = CATEGORY_LABEL_TO_DB.get(category_label, category_label)
    partners = await get_restaurants_by_region_and_category(region_name, category_db)
    if not partners:
        await message.answer(f"В категории «{category_label}» пока нет партнёров.")
        return

    markup = get_restaurants_keyboard(partners)
    await message.answer(
        f"📍 {region_name} → {category_label}\n\nВыберите партнёра:",
        reply_markup=markup
    )
    await state.update_data(selected_category=category_label, selected_category_db=category_db)
    await state.set_state(BotStates.waiting_restaurant)

# Обработчики как отдельные функции


async def handle_region_selection(message: Message, state: FSMContext):
    """Обработка выбора района Бали"""
    if message.text == "🔐 Вернуться в админское меню":
        role, status = (await get_user_role(message))[0]
        if role == 'admin':
            from handlers.common import main_menu
            await main_menu(message, state)
        else:
            await show_regions_or_restaurants(message, state, is_admin=False)
        return

    region_name = message.text
    try:
        await show_region_categories(message, state, region_name, is_admin=False)
    except Exception as e:
        await log_error(e, f"region_selection_{region_name}")
        await message.answer("Ошибка загрузки категорий.")
        await show_regions_or_restaurants(message, state, is_admin=False)


async def handle_category_selection(message: Message, state: FSMContext):
    """Обработка выбора категории партнёров"""
    text = message.text
    data = await state.get_data()
    region_name = data.get('selected_region', '')

    if text == "⬅️ Назад к районам":
        await show_regions_or_restaurants(message, state, is_admin=False)
        return

    if text == "🏠 Вернуться в главное меню":
        from handlers.common import main_menu
        await main_menu(message, state)
        return

    if text not in CATEGORY_LABEL_TO_DB:
        await message.answer("Пожалуйста, выберите категорию из списка.")
        return

    try:
        await show_category_partners(message, state, region_name, text)
    except Exception as e:
        await log_error(e, f"category_selection_{text}")
        await message.answer("Ошибка загрузки партнёров.")
        await show_region_categories(message, state, region_name)


async def handle_restaurant_selection(message: Message, state: FSMContext):
    """Обработка выбора партнёра"""
    text = message.text

    if text == "🏠 Вернуться в главное меню":
        from handlers.common import main_menu
        await main_menu(message, state)
        return

    if text in ("⬅️ Назад к категориям", "⬅️ Назад к районам"):
        data = await state.get_data()
        region_name = data.get('selected_region', '')
        if region_name:
            await show_region_categories(message, state, region_name)
        else:
            await show_regions_or_restaurants(message, state)
        return

    restaurant = text
    info = await get_restaurant_info(restaurant)

    if len(info) > 0:
        markup = get_restaurant_info_keyboard()
        await message.answer('Что вам интересно?', reply_markup=markup)
        await state.update_data(restaurant_info=info[0])
        await state.set_state(BotStates.waiting_menu_action)
    else:
        await message.answer("Партнёр не найден. Выберите из списка.")


async def handle_banquet_restaurant_selection(message: Message, state: FSMContext):
    """Обработка выбора банкетного ресторана"""
    if message.text == '↩️ Вернуться назад':
        data = await state.get_data()
        region_name = data.get('selected_region')
        if region_name:
            await show_region_restaurants(message, state, region_name, is_admin=False)
        else:
            from handlers.common import main_menu
            await main_menu(message, state)
        return

    restaurant_name = message.text

    try:
        banquet_restaurants = await get_banquet_restaurants()
        restaurant_names = [r[0] for r in banquet_restaurants]

        if restaurant_name not in restaurant_names:
            await message.answer("Выбранный ресторан не поддерживает банкеты. Выберите из предложенного списка.")
            return

        restaurant_info = await get_restaurant_info(restaurant_name)
        banquet_folder_path = f"{MENU_PATH}/{restaurant_name}/Банкет"

        try:
            if not os.path.exists(banquet_folder_path):
                await message.answer(
                    f"К сожалению, информация о банкетах для {restaurant_name} временно недоступна.\n"
                    "Обратитесь к менеджеру для получения подробной информации."
                )
                return

            banquet_files = []
            for file in os.listdir(banquet_folder_path):
                file_path = os.path.join(banquet_folder_path, file)
                if os.path.isfile(file_path):
                    banquet_files.append((file, file_path))

            if not banquet_files:
                await message.answer(
                    f"В папке банкетов для {restaurant_name} нет доступных файлов.\n"
                    "Обратитесь к менеджеру для получения информации."
                )
                return

            for file_name, file_path in banquet_files:
                try:
                    document = FSInputFile(file_path)
                    await message.answer_document(
                        document,
                        caption=f"📄 {file_name}" if len(
                            banquet_files) > 1 else f"📋 Информация о банкетах в {restaurant_name}"
                    )
                    if len(banquet_files) > 1:
                        await asyncio.sleep(0.5)
                except Exception as file_error:
                    logger.error(
                        f"Ошибка отправки файла {file_name}: {file_error}")
                    await message.answer(f"❌ Не удалось отправить файл: {file_name}")

            reservation_info = restaurant_info[0][2] if restaurant_info else "Номер резервирования недоступен"

            buttons = [[KeyboardButton(text="↩️ Вернуться назад")]]
            markup = ReplyKeyboardMarkup(
                keyboard=buttons, resize_keyboard=True)

            await message.answer(
                f"""Для бронирования:\n📋 {reservation_info}""",
                reply_markup=markup
            )

        except PermissionError:
            await log_error(f"Permission denied for {banquet_folder_path}", f"banquet_permission_{restaurant_name}")
            await message.answer(
                f"Нет доступа к файлам банкетов для {restaurant_name}.\n"
                "Обратитесь к администратору."
            )
        except Exception as e:
            await log_error(e, f"banquet_files_send_{restaurant_name}")
            await message.answer(
                f"Произошла ошибка при отправке файлов банкетов для {restaurant_name}.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
    except Exception as e:
        await log_error(e, f"banquet_restaurant_selection_{restaurant_name}")
        await message.answer("Произошла ошибка при обработке запроса.")


async def handle_promotions_events_from_viewing(message: Message, state: FSMContext):
    """Обработка акций и событий из состояний просмотра"""
    data = await state.get_data()
    restaurant_id = data.get('restaurant_id')

    if not restaurant_id:
        # Если restaurant_id не найден, пытаемся получить из restaurant_info
        info = data.get('restaurant_info')
        if info:
            # info может быть кортежем или списком кортежей
            if isinstance(info, list) and len(info) > 0:
                restaurant_name = info[0][0] if isinstance(
                    info[0], (list, tuple)) else str(info[0])
            elif isinstance(info, tuple):
                restaurant_name = info[0] if len(info) > 0 else None
            else:
                restaurant_name = str(info) if info else None

            if restaurant_name:
                restaurant_id = await get_restaurant_id_by_name(restaurant_name)

    if message.text == "🎁 Спец. предложения/Коллаборации":
        if restaurant_id:
            promotions = await get_promotions(restaurant_id, status='approved')

            if not promotions:
                await message.answer("📋 Акций пока нет.")
                return

            # Показываем последнюю акцию (первую в списке, т.к. они отсортированы по created_at DESC)
            await show_promotion_event(message, state, promotions, 0, 'promotion', restaurant_id)
        else:
            await message.answer("Ошибка: ресторан не найден.")

    elif message.text == "🎊 События":
        if restaurant_id:
            events = await get_events(restaurant_id, status='approved')

            if not events:
                await message.answer("📋 Событий пока нет.")
                return

            # Показываем последнее событие (первое в списке, т.к. они отсортированы по created_at DESC)
            await show_promotion_event(message, state, events, 0, 'event', restaurant_id)
        else:
            await message.answer("Ошибка: ресторан не найден.")

    elif message.text == "📋 Меню":
        # Переключаемся на состояние waiting_menu_action и обрабатываем меню
        info = data.get('restaurant_info')
        if not info:
            await message.answer("Ошибка: информация о ресторане не найдена.")
            return

        buttons = [
            [KeyboardButton(text="⬅️ Назад к ресторану")],
            [KeyboardButton(text="⬅️ Назад к ресторанам региона")],
        ]

        try:
            for file in os.listdir(f"{MENU_PATH}/{info[0]}"):
                file_path = os.path.join(f"{MENU_PATH}/{info[0]}", file)
                if os.path.isfile(file_path):
                    buttons.append([KeyboardButton(text=file.split('.')[0])])
        except FileNotFoundError:
            await message.answer("Меню временно недоступно")
            return

        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer(f'{info[0]} меню', reply_markup=markup)
        await state.set_state(BotStates.waiting_menu_item)
        return

    elif message.text == "🎉 Заказать банкет":
        # Обрабатываем банкет напрямую
        info = data.get('restaurant_info')
        if not info:
            await message.answer("Ошибка: информация о ресторане не найдена.")
            return

        restaurant_name = info[0]
        banquet_folder_path = f"{MENU_PATH}/{restaurant_name}/Банкет"

        if not os.path.exists(banquet_folder_path):
            await message.answer(
                f"Папка банкетов для {restaurant_name} не найдена.\n"
                "Обратитесь к менеджеру для получения информации."
            )
            return

        banquet_files = []
        for file in os.listdir(banquet_folder_path):
            file_path = os.path.join(banquet_folder_path, file)
            if os.path.isfile(file_path) and file.lower().endswith('.pdf'):
                banquet_files.append((file, file_path))

        if not banquet_files:
            await message.answer(
                f"В папке банкетов для {restaurant_name} нет доступных файлов.\n"
                "Обратитесь к менеджеру для получения информации."
            )
            return

        # Отправляем сообщение о подготовке банкетного предложения
        loading_msg = await message.answer("⏳ Сейчас подготовлю для вас банкетное предложение, пожалуйста подождите...")

        # Отправляем каждый PDF как изображения
        files_sent = False
        for file_idx, (file_name, file_path) in enumerate(banquet_files):
            try:
                image_files = await pdf_to_images(file_path)

                if not image_files:
                    await message.answer(f"Не удалось конвертировать PDF {file_name} в изображения.")
                    continue

                file_ids = load_telegram_file_ids(file_path)
                total_pages = len(image_files)
                captions = []
                for i in range(total_pages):
                    page_num = i + 1
                    caption = f"📄 {file_name.replace('.pdf', '')} (страница {page_num} из {total_pages})" if total_pages > 1 else f"📄 {file_name.replace('.pdf', '')}"
                    captions.append(caption)

                try:
                    sent_messages = await send_photos_as_media_group(message, image_files, captions=captions, file_ids=file_ids)
                    if file_ids:
                        save_telegram_file_ids(file_path, file_ids)
                    files_sent = True
                except Exception as e:
                    logger.error(
                        f"Ошибка отправки media group для {file_name}: {e}")
                    # Fallback на отправку по одному
                    new_file_ids = {}
                    for i, image_path in enumerate(image_files):
                        page_num = i + 1
                        caption = captions[i]
                        try:
                            if page_num in file_ids:
                                sent_message = await send_photo_with_caption(message, file_ids[page_num], caption)
                            else:
                                photo = FSInputFile(image_path)
                                sent_message = await send_photo_with_caption(message, photo, caption)
                            if sent_message.photo:
                                new_file_ids[page_num] = sent_message.photo[-1].file_id
                            if i < len(image_files) - 1:
                                await asyncio.sleep(0.2)
                        except Exception as e2:
                            logger.error(
                                f"Ошибка отправки фото {page_num}: {e2}")
                    if new_file_ids:
                        file_ids.update(new_file_ids)
                        save_telegram_file_ids(file_path, file_ids)

                files_sent = True
            except Exception as e:
                logger.error(
                    f"Ошибка обработки банкетного файла {file_name}: {e}")

        # Удаляем сообщение о загрузке после отправки всех файлов банкета
        if files_sent:
            try:
                await loading_msg.delete()
            except:
                pass
        return

    elif message.text == "📍 Адрес":
        # Показываем адрес
        info = data.get('restaurant_info')
        if info and len(info) > 7:
            await message.answer(info[7])
        else:
            await message.answer("Адрес не указан.")
        await state.set_state(BotStates.waiting_menu_action)
        return

    elif message.text == "🚚 Доставка":
        # Показываем информацию о доставке
        info = data.get('restaurant_info')
        if info and len(info) > 3:
            await message.answer(info[3])
        else:
            await message.answer("Информация о доставке не указана.")
        await state.set_state(BotStates.waiting_menu_action)
        return

    elif message.text in ["⬅️ Назад к ресторанам региона", "🏠 Вернуться в главное меню"]:
        # Возвращаемся к состоянию waiting_menu_action и обрабатываем навигацию
        await state.set_state(BotStates.waiting_menu_action)
        # Вызываем обработчик напрямую, чтобы избежать двойной обработки
        if message.text == "🏠 Вернуться в главное меню":
            from handlers.common import main_menu
            await main_menu(message, state)
        elif message.text == "⬅️ Назад к ресторанам региона":
            region_name = data.get('selected_region')
            await show_region_restaurants(message, state, region_name, is_admin=False)
        return

    else:
        # Если это не известная команда, возвращаемся к меню ресторана
        info = data.get('restaurant_info')
        if info:
            markup = get_restaurant_info_keyboard()
            await message.answer('Что вам интересно?', reply_markup=markup)
            await state.set_state(BotStates.waiting_menu_action)
        else:
            from handlers.common import main_menu
            await main_menu(message, state)


async def handle_menu_action(message: Message, state: FSMContext):
    """Обработка действий с меню ресторана"""
    data = await state.get_data()
    info = data.get('restaurant_info')

    if message.text == '🏠 Вернуться в главное меню':
        from handlers.common import main_menu
        await main_menu(message, state)
        return

    if message.text == "⬅️ Назад к ресторанам региона":
        data = await state.get_data()
        region_name = data.get('selected_region')
        await show_region_restaurants(message, state, region_name, is_admin=False)
        return

    if message.text == "📋 Меню":
        buttons = [
            [KeyboardButton(text="⬅️ Назад к ресторану")],
            [KeyboardButton(text="⬅️ Назад к ресторанам региона")],
        ]

        try:
            for file in os.listdir(f"{MENU_PATH}/{info[0]}"):
                file_path = os.path.join(f"{MENU_PATH}/{info[0]}", file)
                if os.path.isfile(file_path):
                    buttons.append([KeyboardButton(text=file.split('.')[0])])
        except FileNotFoundError:
            await message.answer("Меню временно недоступно")
            return

        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer(f'{info[0]} меню', reply_markup=markup)
        await state.set_state(BotStates.waiting_menu_item)

    elif message.text == "🎉 Заказать банкет":
        # Обработка заказа банкета - используем тот же ресторан
        restaurant_name = info[0]
        restaurant_info = await get_restaurant_info(restaurant_name)
        banquet_folder_path = f"{MENU_PATH}/{restaurant_name}/Банкет"

        try:
            if not os.path.exists(banquet_folder_path):
                await message.answer(
                    f"К сожалению, информация о банкетах для {restaurant_name} временно недоступна.\n"
                    "Обратитесь к менеджеру для получения подробной информации."
                )
                return

            banquet_files = []
            for file in os.listdir(banquet_folder_path):
                file_path = os.path.join(banquet_folder_path, file)
                if os.path.isfile(file_path) and file.lower().endswith('.pdf'):
                    banquet_files.append((file, file_path))

            if not banquet_files:
                await message.answer(
                    f"В папке банкетов для {restaurant_name} нет доступных файлов.\n"
                    "Обратитесь к менеджеру для получения информации."
                )
                return

            # Отправляем сообщение о подготовке банкетного предложения
            loading_msg = await message.answer("⏳ Сейчас подготовлю для вас банкетное предложение, пожалуйста подождите...")

            # Отправляем каждый PDF как изображения (как в меню)
            files_sent = False
            for file_idx, (file_name, file_path) in enumerate(banquet_files):
                try:
                    # Конвертируем PDF в изображения (с кэшированием)
                    image_files = await pdf_to_images(file_path)

                    if not image_files:
                        await message.answer(f"Не удалось конвертировать PDF {file_name} в изображения.")
                        continue

                    # Проверяем, есть ли сохраненные Telegram file_id
                    file_ids = load_telegram_file_ids(file_path)
                    total_pages = len(image_files)

                    # Формируем подписи для каждой страницы
                    captions = []
                    for i in range(total_pages):
                        page_num = i + 1
                        caption = f"📄 {file_name.replace('.pdf', '')} (страница {page_num} из {total_pages})" if total_pages > 1 else f"📄 {file_name.replace('.pdf', '')}"
                        captions.append(caption)

                    # Отправляем все фото группой (media group)
                    try:
                        sent_messages = await send_photos_as_media_group(
                            message,
                            image_files,
                            captions=captions,
                            file_ids=file_ids
                        )

                        # Сохраняем file_id из ответа
                        if file_ids:
                            save_telegram_file_ids(file_path, file_ids)
                    except Exception as e:
                        logger.error(
                            f"Ошибка отправки media group для {file_name}: {e}")
                        # Если не удалось отправить группой, отправляем по одному
                        new_file_ids = {}
                        for i, image_path in enumerate(image_files):
                            page_num = i + 1
                            caption = captions[i]

                            try:
                                if page_num in file_ids:
                                    sent_message = await send_photo_with_caption(message, file_ids[page_num], caption)
                                else:
                                    photo = FSInputFile(image_path)
                                    sent_message = await send_photo_with_caption(message, photo, caption)

                                if sent_message.photo:
                                    new_file_ids[page_num] = sent_message.photo[-1].file_id

                                if i < len(image_files) - 1:
                                    await asyncio.sleep(0.2)
                            except Exception as e2:
                                logger.error(
                                    f"Ошибка отправки фото {page_num}: {e2}")

                        if new_file_ids:
                            file_ids.update(new_file_ids)
                            save_telegram_file_ids(file_path, file_ids)

                    # Задержка между файлами
                    if banquet_files.index((file_name, file_path)) < len(banquet_files) - 1:
                        await asyncio.sleep(0.5)

                    files_sent = True

                except Exception as file_error:
                    logger.error(
                        f"Ошибка отправки файла {file_name}: {file_error}")
                    await message.answer(f"❌ Не удалось отправить файл: {file_name}")

            # Удаляем сообщение о загрузке после отправки всех файлов банкета
            if files_sent:
                try:
                    await loading_msg.delete()
                except:
                    pass

            reservation_info = restaurant_info[0][2] if restaurant_info else "Номер резервирования недоступен"

            await message.answer(
                f"""Для бронирования:\n📋 {reservation_info}"""
            )

        except PermissionError:
            await log_error(f"Permission denied for {banquet_folder_path}", f"banquet_permission_{restaurant_name}")
            await message.answer(
                f"Нет доступа к файлам банкетов для {restaurant_name}.\n"
                "Обратитесь к администратору."
            )
        except Exception as e:
            await log_error(e, f"banquet_files_send_{restaurant_name}")
            await message.answer(
                f"Произошла ошибка при отправке файлов банкетов для {restaurant_name}.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
    elif message.text == "🚚 Доставка":
        await message.answer(info[3])
    elif message.text == "🎁 Спец. предложения/Коллаборации":
        # Получаем акции ресторана
        # info - это кортеж из get_restaurant_info, где первый элемент - название ресторана
        if isinstance(info, (list, tuple)) and len(info) > 0:
            restaurant_name = info[0] if isinstance(info[0], str) else (
                info[0][0] if isinstance(info[0], (list, tuple)) else str(info[0]))
        else:
            restaurant_name = str(info) if info else None
        restaurant_id = await get_restaurant_id_by_name(restaurant_name) if restaurant_name else None

        if restaurant_id:
            promotions = await get_promotions(restaurant_id, status='approved')

            if not promotions:
                await message.answer("📋 Акций пока нет.")
                return

            # Показываем последнюю акцию (первую в списке, т.к. они отсортированы по created_at DESC)
            await show_promotion_event(message, state, promotions, 0, 'promotion', restaurant_id)
        else:
            await message.answer("Ошибка: ресторан не найден.")

    elif message.text == "🎊 События":
        # Получаем события ресторана
        # info - это кортеж из get_restaurant_info, где первый элемент - название ресторана
        if isinstance(info, (list, tuple)) and len(info) > 0:
            restaurant_name = info[0] if isinstance(info[0], str) else (
                info[0][0] if isinstance(info[0], (list, tuple)) else str(info[0]))
        else:
            restaurant_name = str(info) if info else None
        restaurant_id = await get_restaurant_id_by_name(restaurant_name) if restaurant_name else None

        if restaurant_id:
            events = await get_events(restaurant_id, status='approved')

            if not events:
                await message.answer("📋 Событий пока нет.")
                return

            # Показываем последнее событие (первое в списке, т.к. они отсортированы по created_at DESC)
            await show_promotion_event(message, state, events, 0, 'event', restaurant_id)
        else:
            await message.answer("Ошибка: ресторан не найден.")
    elif message.text == "📍 Адрес":
        await message.answer(info[7])
    else:
        await message.answer("Неизвестная команда. Выберите из предложенных вариантов.")


async def handle_menu_item(message: Message, state: FSMContext):
    """Обработка выбора пункта меню"""
    data = await state.get_data()
    info = data.get('restaurant_info')

    if message.text == '⬅️ Назад к ресторану':
        markup = get_restaurant_info_keyboard()
        await message.answer('Что вам интересно?', reply_markup=markup)
        await state.set_state(BotStates.waiting_menu_action)
    elif message.text == '⬅️ Назад к ресторанам региона':
        data = await state.get_data()
        region_name = data.get('selected_region')
        await show_region_restaurants(message, state, region_name, is_admin=False)
        return
    else:
        try:
            pdf_path = f"{MENU_PATH}/{info[0]}/{message.text}.pdf"

            # Отправляем сообщение о подготовке меню
            loading_msg = await message.answer("⏳ Сейчас подготовлю для вас меню, пожалуйста подождите...")

            # Конвертируем PDF в изображения (с кэшированием)
            try:
                image_files = await pdf_to_images(pdf_path)

                if not image_files:
                    # Удаляем сообщение о загрузке при ошибке
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                    await message.answer("Не удалось конвертировать PDF в изображения.")
                    return

                # Проверяем, есть ли сохраненные Telegram file_id
                file_ids = load_telegram_file_ids(pdf_path)
                total_pages = len(image_files)

                # Формируем подписи для каждой страницы
                captions = []
                for i in range(total_pages):
                    page_num = i + 1
                    caption = f"📄 {message.text} (страница {page_num} из {total_pages})" if total_pages > 1 else f"📄 {message.text}"
                    captions.append(caption)

                # Отправляем все фото группой (media group)
                try:
                    sent_messages = await send_photos_as_media_group(
                        message,
                        image_files,
                        captions=captions,
                        file_ids=file_ids
                    )

                    # Сохраняем file_id из ответа
                    if file_ids:
                        save_telegram_file_ids(pdf_path, file_ids)

                    # Удаляем сообщение о загрузке после успешной отправки всех файлов
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                except Exception as e:
                    logger.error(f"Ошибка отправки media group для меню: {e}")
                    # Если не удалось отправить группой, отправляем по одному
                    new_file_ids = {}
                    for i, image_path in enumerate(image_files):
                        page_num = i + 1
                        caption = captions[i]

                        try:
                            if page_num in file_ids:
                                sent_message = await send_photo_with_caption(message, file_ids[page_num], caption)
                            else:
                                photo = FSInputFile(image_path)
                                sent_message = await send_photo_with_caption(message, photo, caption)

                            if sent_message.photo:
                                new_file_ids[page_num] = sent_message.photo[-1].file_id

                            if i < len(image_files) - 1:
                                await asyncio.sleep(0.2)
                        except Exception as e2:
                            logger.error(
                                f"Ошибка отправки фото {page_num}: {e2}")

                    if new_file_ids:
                        file_ids.update(new_file_ids)
                        save_telegram_file_ids(pdf_path, file_ids)

                    # Удаляем сообщение о загрузке после отправки всех файлов (даже если была ошибка)
                    try:
                        await loading_msg.delete()
                    except:
                        pass

            except FileNotFoundError:
                await message.answer("Файл не найден. Возвращаемся в меню ресторана.")
                await handle_menu_action(message, state)
            except Exception as e:
                await log_error(e, f"pdf_conversion_error_{message.text}")
                # Если конвертация не удалась, пробуем отправить PDF как документ
                try:
                    document = FSInputFile(pdf_path)
                    await message.answer_document(document, caption=f"📄 {message.text}")
                except Exception as e2:
                    await log_error(e2, f"menu_item_error_{message.text}")
                    await message.answer("Ошибка при отправке файла.")
                    await handle_menu_action(message, state)

        except Exception as e:
            await log_error(e, f"menu_item_error_{message.text}")
            await message.answer("Ошибка при отправке файла.")
            await handle_menu_action(message, state)


async def show_promotion_event(message: Message, state: FSMContext, items: list, index: int, item_type: str, restaurant_id: int):
    """Показать акцию или событие с навигацией"""
    if not items or index < 0 or index >= len(items):
        return

    item = items[index]
    emoji = "🎁" if item_type == 'promotion' else "🎊"

    text = f"{emoji} {item['title']}\n\n"
    if item.get('description'):
        text += f"{item['description']}\n"

    # Создаем клавиатуру для навигации
    markup = get_promotion_event_view_keyboard(index, len(items), item_type)

    # Сохраняем данные в state для навигации
    await state.update_data(
        promotions_list=items if item_type == 'promotion' else None,
        events_list=items if item_type == 'event' else None,
        current_index=index,
        restaurant_id=restaurant_id,
        viewing_type=item_type
    )

    # Устанавливаем состояние
    if item_type == 'promotion':
        await state.set_state(BotStates.viewing_promotions)
    else:
        await state.set_state(BotStates.viewing_events)

    # Если есть фото, отправляем с фото
    if item.get('photo_file_id'):
        try:
            await message.answer_photo(
                item['photo_file_id'],
                caption=text,
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото {item_type}: {e}")
            await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def handle_promotion_event_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по акциям/событиям"""
    data = callback.data
    data_parts = data.split('_')

    # Формат: view_promotion_next_0 или view_event_prev_1
    if len(data_parts) < 4:
        await callback.answer()
        return

    action = data_parts[2]  # 'next' или 'prev'
    current_index = int(data_parts[3])
    item_type = data_parts[1]  # 'promotion' или 'event'

    state_data = await state.get_data()

    if item_type == 'promotion':
        items = state_data.get('promotions_list')
        new_state = BotStates.viewing_promotions
    else:
        items = state_data.get('events_list')
        new_state = BotStates.viewing_events

    if not items:
        await callback.answer("Ошибка: список не найден", show_alert=True)
        return

    # Вычисляем новый индекс
    if action == 'next':
        new_index = current_index + 1
    else:  # prev
        new_index = current_index - 1

    if new_index < 0 or new_index >= len(items):
        await callback.answer()
        return

    # Показываем новую акцию/событие
    restaurant_id = state_data.get('restaurant_id')
    if restaurant_id:
        item = items[new_index]
        emoji = "🎁" if item_type == 'promotion' else "🎊"

        text = f"{emoji} {item['title']}\n\n"
        if item.get('description'):
            text += f"{item['description']}\n"

        # Создаем клавиатуру для навигации
        markup = get_promotion_event_view_keyboard(
            new_index, len(items), item_type)

        # Обновляем данные в state
        await state.update_data(
            current_index=new_index
        )

        # Редактируем сообщение вместо удаления
        try:
            if item.get('photo_file_id'):
                # Если есть фото, проверяем, было ли предыдущее сообщение с фото
                if callback.message.photo:
                    # Если было фото, редактируем медиа
                    try:
                        await callback.message.edit_media(
                            media=InputMediaPhoto(
                                media=item['photo_file_id'],
                                caption=text
                            ),
                            reply_markup=markup
                        )
                    except Exception as e:
                        logger.error(f"Ошибка редактирования медиа: {e}")
                        # Если не удалось отредактировать, отправляем новое сообщение
                        await callback.message.delete()
                        await callback.message.answer_photo(
                            item['photo_file_id'],
                            caption=text,
                            reply_markup=markup
                        )
                else:
                    # Если предыдущее сообщение было текстовым, удаляем и отправляем новое с фото
                    await callback.message.delete()
                    await callback.message.answer_photo(
                        item['photo_file_id'],
                        caption=text,
                        reply_markup=markup
                    )
            else:
                # Если нет фото, редактируем текст
                if callback.message.photo:
                    # Если предыдущее сообщение было с фото, удаляем и отправляем текстовое
                    await callback.message.delete()
                    await callback.message.answer(text, reply_markup=markup)
                else:
                    # Если было текстовое, редактируем текст
                    await callback.message.edit_text(
                        text,
                        reply_markup=markup
                    )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            try:
                await callback.message.delete()
            except:
                pass
            await show_promotion_event(callback.message, state, items, new_index, item_type, restaurant_id)
    else:
        await callback.answer("Ошибка: ресторан не найден", show_alert=True)

    await callback.answer()


def register_user_handlers(dp, bot):
    """Регистрация обработчиков для пользователей"""
    from aiogram import F
    from aiogram.types import CallbackQuery

    dp.message.register(handle_region_selection,
                        StateFilter(BotStates.waiting_region))
    dp.message.register(handle_category_selection,
                        StateFilter(BotStates.waiting_category))
    dp.message.register(handle_restaurant_selection,
                        StateFilter(BotStates.waiting_restaurant))
    dp.message.register(handle_banquet_restaurant_selection,
                        StateFilter(BotStates.waiting_banquet_restaurant))
    dp.message.register(handle_menu_action, StateFilter(
        BotStates.waiting_menu_action))
    dp.message.register(handle_menu_item, StateFilter(
        BotStates.waiting_menu_item))

    # Обработчики для акций и событий из состояний просмотра
    dp.message.register(handle_promotions_events_from_viewing,
                        StateFilter(BotStates.viewing_promotions))
    dp.message.register(handle_promotions_events_from_viewing,
                        StateFilter(BotStates.viewing_events))

    # Обработчики навигации по акциям и событиям
    dp.callback_query.register(handle_promotion_event_navigation, lambda c: c.data.startswith(
        "view_promotion_") or c.data.startswith("view_event_"))

    logger.info("User handlers зарегистрированы")
