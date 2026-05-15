"""Утилита для конвертации PDF в изображения с кэшированием"""
import os
import hashlib
import asyncio
import json
from pathlib import Path
from typing import Optional
from pdf2image import convert_from_path
from PIL import Image
import logging
from config import CACHE_PATH

logger = logging.getLogger(__name__)

# Создаем папку для кэша, если её нет
os.makedirs(CACHE_PATH, exist_ok=True)

def get_pdf_hash(pdf_path: str) -> str:
    """Получить хэш PDF файла для использования в имени кэша"""
    with open(pdf_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return file_hash

def get_cache_path(pdf_path: str) -> Path:
    """Получить путь к папке кэша для конкретного PDF"""
    pdf_hash = get_pdf_hash(pdf_path)
    pdf_name = Path(pdf_path).stem
    cache_dir = Path(CACHE_PATH) / f"{pdf_name}_{pdf_hash}"
    return cache_dir

def _convert_pdf_sync(pdf_path: str, cache_dir: Path) -> list[str]:
    """Синхронная функция конвертации PDF (вызывается в executor)"""
    # Конвертируем PDF в изображения
    # Используем dpi=120 для агрессивной оптимизации размера файлов (цель: не более 300 КБ на файл)
    logger.info(f"Начинаем конвертацию PDF: {pdf_path}")
    try:
        images = convert_from_path(
            pdf_path, 
            dpi=120,  # Сниженный DPI для агрессивной оптимизации размера
            fmt='png',
            thread_count=1  # Избегаем проблем с многопоточностью
        )
        logger.info(f"PDF конвертирован, получено {len(images)} страниц")
    except Exception as e:
        logger.warning(f"Ошибка конвертации с dpi=120: {e}")
        # Пробуем с меньшим DPI
        try:
            logger.info("Пробуем конвертацию с dpi=100...")
            images = convert_from_path(pdf_path, dpi=100, fmt='png', thread_count=1)
            logger.info(f"PDF конвертирован с dpi=100, получено {len(images)} страниц")
        except Exception as e2:
            logger.error(f"Ошибка конвертации с dpi=100: {e2}")
            raise
    
    # Сохраняем изображения в кэш
    image_files = []
    total_pages = len(images)
    logger.info(f"Начинаем сохранение {total_pages} страниц в кэш...")
    
    for i, image in enumerate(images):
        if (i + 1) % 5 == 0 or i == 0:
            logger.info(f"Обрабатываем страницу {i+1}/{total_pages}...")
        image_path = cache_dir / f"page_{i+1:03d}.png"
        
        # Проверяем, что изображение не пустое
        if image.size[0] == 0 or image.size[1] == 0:
            logger.warning(f"Пропущена пустая страница {i+1} в {pdf_path}")
            continue
        
        # Сохраняем исходный режим для логирования
        original_mode = image.mode
        
        # Проверяем исходное изображение на белизну (до конвертации)
        try:
            # Быстрая проверка - берем несколько пикселей из разных мест
            check_pixels = [
                image.getpixel((0, 0)) if image.mode == 'RGB' else image.getpixel((0, 0))[:3] if len(image.getpixel((0, 0))) > 3 else image.getpixel((0, 0)),
                image.getpixel((min(10, image.width-1), min(10, image.height-1))) if image.mode == 'RGB' else image.getpixel((min(10, image.width-1), min(10, image.height-1)))[:3] if len(image.getpixel((min(10, image.width-1), min(10, image.height-1)))) > 3 else image.getpixel((min(10, image.width-1), min(10, image.height-1))),
            ]
            # Для RGBA проверяем только RGB компоненты
            if original_mode == 'RGBA':
                check_pixels = [p[:3] if isinstance(p, tuple) and len(p) > 3 else p for p in check_pixels]
        except:
            check_pixels = []
        
        # Конвертируем в RGB, если нужно (для PNG с прозрачностью)
        # Это важно для правильного отображения изображений
        if image.mode in ('RGBA', 'LA'):
            # Создаем белый фон для прозрачных изображений
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'RGBA':
                # Используем альфа-канал как маску для правильной вставки
                # Важно: paste с mask требует, чтобы изображение было в том же режиме, что и фон
                # Сначала конвертируем RGBA в RGB, затем вставляем с маской
                rgb_temp = image.convert('RGB')
                alpha = image.split()[-1]  # Альфа-канал (последний канал в RGBA)
                # Вставляем RGB изображение на белый фон, используя альфа-канал как маску
                rgb_image.paste(rgb_temp, (0, 0), mask=alpha)
            else:  # LA (Luminance + Alpha)
                # Конвертируем LA в RGB, игнорируя альфа-канал (он уже учтен в яркости)
                rgb_image.paste(image.convert('RGB'))
            image = rgb_image
        elif image.mode == 'P':
            # Палитровые изображения конвертируем через RGBA
            if 'transparency' in image.info:
                rgba_image = image.convert('RGBA')
                rgb_image = Image.new('RGB', rgba_image.size, (255, 255, 255))
                rgb_image.paste(rgba_image.convert('RGB'), mask=rgba_image.split()[-1])
                image = rgb_image
            else:
                image = image.convert('RGB')
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Проверяем, что изображение не полностью белое (после конвертации)
        # Это может указывать на проблему с конвертацией
        try:
            # Берем небольшую выборку пикселей для проверки (не только из угла, но и из центра)
            sample_size = min(100, image.width, image.height)
            samples = [
                image.crop((0, 0, sample_size, sample_size)),  # Левый верхний угол
                image.crop((image.width - sample_size, image.height - sample_size, image.width, image.height)),  # Правый нижний угол
                image.crop((image.width // 2 - sample_size // 2, image.height // 2 - sample_size // 2, 
                           image.width // 2 + sample_size // 2, image.height // 2 + sample_size // 2))  # Центр
            ]
            
            all_white = True
            for sample in samples:
                colors = sample.getcolors(maxcolors=256*256*256)
                if colors:
                    # Проверяем, не все ли пиксели белые
                    non_white_colors = [c for c in colors if c[1] != (255, 255, 255)]
                    if non_white_colors:
                        all_white = False
                        break
            
            if all_white:
                logger.warning(f"⚠️ Страница {i+1} в {pdf_path} выглядит полностью белой! Размер: {image.size}, режим до конвертации: {images[i].mode if i < len(images) else 'unknown'}")
        except Exception as check_error:
            logger.debug(f"Ошибка при проверке белого изображения: {check_error}")
        
        # Оптимизируем размер изображения перед сохранением
        # Цель: каждый файл не более 300 КБ
        max_dimension = 1600  # Максимальный размер по любой стороне (уменьшено для агрессивной оптимизации)
        max_file_size_bytes = 300 * 1024  # 300 КБ в байтах
        
        if image.width > max_dimension or image.height > max_dimension:
            # Вычисляем коэффициент масштабирования
            scale = min(max_dimension / image.width, max_dimension / image.height)
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            logger.debug(f"Уменьшаем страницу {i+1} с {image.size} до ({new_width}, {new_height})")
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Пробуем сохранить как JPEG для лучшего сжатия (меню обычно не требует прозрачности)
        # JPEG лучше сжимает фотографии и сканированные документы
        jpeg_path = cache_dir / f"page_{i+1:03d}.jpg"
        quality = 75  # Начальное качество JPEG (снижено для агрессивной оптимизации)
        saved = False
        max_attempts = 20  # Увеличиваем количество попыток для более агрессивной оптимизации
        
        for attempt in range(max_attempts):
            image.save(jpeg_path, 'JPEG', quality=quality, optimize=True)
            file_size = os.path.getsize(jpeg_path)
            
            if file_size <= max_file_size_bytes:
                # Размер подходит, используем JPEG
                image_files.append(str(jpeg_path))
                saved = True
                logger.debug(f"Страница {i+1} сохранена как JPEG с качеством {quality} (размер: {file_size / 1024:.1f} KB)")
                break
            else:
                # Файл слишком большой, агрессивно уменьшаем качество или размер
                if quality > 50:
                    quality -= 5  # Снижаем качество быстрее
                elif quality > 40 and (image.width > 1400 or image.height > 1400):
                    quality -= 3  # Продолжаем снижать качество
                elif image.width > 1400 or image.height > 1400:
                    # Уменьшаем размер изображения и сбрасываем качество
                    scale = 0.85  # Более агрессивное уменьшение
                    new_width = int(image.width * scale)
                    new_height = int(image.height * scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    quality = 70  # Сбрасываем качество для повторной оптимизации
                    logger.debug(f"Уменьшаем страницу {i+1} до ({new_width}, {new_height}), качество сброшено до {quality}")
                elif image.width > 1200 or image.height > 1200:
                    # Еще одно уменьшение размера
                    scale = 0.9
                    new_width = int(image.width * scale)
                    new_height = int(image.height * scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    quality = max(quality, 55)  # Не повышаем качество, только поддерживаем минимум
                    logger.debug(f"Дополнительно уменьшаем страницу {i+1} до ({new_width}, {new_height})")
                elif quality > 40:
                    quality -= 3  # Продолжаем снижать качество
                else:
                    # Если уже достаточно маленькое изображение и очень низкое качество, все равно сохраняем
                    image_files.append(str(jpeg_path))
                    saved = True
                    logger.warning(f"Страница {i+1} сохранена как JPEG с качеством {quality}, но размер больше 300 КБ: {file_size / 1024:.1f} KB ({file_size / (1024*1024):.2f} MB)")
                    break
        
        # Если JPEG не удалось оптимизировать, пробуем PNG
        if not saved:
            logger.debug(f"Пробуем PNG для страницы {i+1}")
            image.save(image_path, 'PNG', optimize=True, compress_level=9)
            file_size = os.path.getsize(image_path)
            
            # Если PNG тоже слишком большой, агрессивно уменьшаем изображение
            if file_size > max_file_size_bytes:
                # Несколько итераций уменьшения, если нужно
                for resize_iteration in range(3):
                    scale = 0.8  # Более агрессивное уменьшение
                    new_width = int(image.width * scale)
                    new_height = int(image.height * scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    image.save(image_path, 'PNG', optimize=True, compress_level=9)
                    file_size = os.path.getsize(image_path)
                    logger.debug(f"Уменьшена страница {i+1} для PNG (итерация {resize_iteration + 1}): {new_width}x{new_height}, размер: {file_size / 1024:.1f} KB")
                    if file_size <= max_file_size_bytes:
                        break
            
            image_files.append(str(image_path))
        
        # Детальное логирование для отладки
        if saved:
            file_size = os.path.getsize(jpeg_path)
        else:
            file_size = os.path.getsize(image_path)
        file_size_kb = file_size / 1024
        file_size_mb = file_size / (1024 * 1024)
        
        if (i + 1) % 5 == 0 or i == 0 or i == total_pages - 1:
            logger.info(f"Сохранена страница {i+1}/{total_pages} (размер: {file_size_kb:.1f} KB / {file_size_mb:.2f} MB)")
        
        # Проверяем, превышает ли файл целевой размер (предупреждение)
        if file_size > max_file_size_bytes:
            logger.warning(f"⚠️ Страница {i+1} сохранена с размером {file_size_mb:.2f} MB ({file_size_kb:.1f} KB, цель: 300 KB)")
        
        # Проверяем размер файла - если он очень маленький, это может указывать на проблему
        if file_size < 1000:  # Меньше 1KB - подозрительно
            logger.warning(f"⚠️ Страница {i+1} сохранена с очень маленьким размером файла: {file_size} байт")
    
    logger.info(f"Все {total_pages} страниц успешно сохранены в кэш")
    
    return image_files

async def pdf_to_images(pdf_path: str) -> list[str]:
    """
    Конвертировать PDF в изображения с кэшированием
    
    Args:
        pdf_path: Путь к PDF файлу
        
    Returns:
        Список путей к изображениям
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")
    
    cache_dir = get_cache_path(pdf_path)
    
    # Проверяем, есть ли уже кэш (поддерживаем как PNG, так и JPEG)
    if cache_dir.exists() and any(cache_dir.iterdir()):
        logger.info(f"Используем кэш для {pdf_path}")
        # Проверяем наличие JPEG файлов (новый формат) или PNG (старый формат)
        image_files = sorted([str(f) for f in cache_dir.glob("*.jpg")])
        if not image_files:
            image_files = sorted([str(f) for f in cache_dir.glob("*.png")])
        if image_files:
            return image_files
    
    # Конвертируем PDF в изображения (в отдельном потоке, т.к. pdf2image синхронная)
    logger.info(f"Конвертируем PDF в изображения: {pdf_path}")
    try:
        # Создаем папку для кэша
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Конвертируем в executor, чтобы не блокировать event loop
        # Добавляем таймаут для очень больших файлов (10 минут)
        loop = asyncio.get_event_loop()
        try:
            image_files = await asyncio.wait_for(
                loop.run_in_executor(None, _convert_pdf_sync, pdf_path, cache_dir),
                timeout=600.0  # 10 минут таймаут
            )
        except asyncio.TimeoutError:
            logger.error(f"Таймаут конвертации PDF {pdf_path} (превышено 10 минут)")
            # Очищаем частично созданный кэш
            import shutil
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            raise TimeoutError(f"Конвертация PDF заняла слишком много времени: {pdf_path}")
        
        logger.info(f"PDF конвертирован в {len(image_files)} изображений")
        return image_files
        
    except Exception as e:
        logger.error(f"Ошибка конвертации PDF {pdf_path}: {e}")
        # Если ошибка, удаляем папку кэша
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
        raise

def get_telegram_file_ids_path(pdf_path: str) -> Path:
    """Получить путь к файлу с Telegram file_id для PDF"""
    cache_dir = get_cache_path(pdf_path)
    return cache_dir / "telegram_file_ids.json"

def save_telegram_file_ids(pdf_path: str, file_ids: dict[int, str]):
    """Сохранить Telegram file_id для страниц PDF"""
    try:
        file_ids_path = get_telegram_file_ids_path(pdf_path)
        file_ids_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_ids_path, 'w', encoding='utf-8') as f:
            json.dump(file_ids, f, ensure_ascii=False, indent=2)
        logger.debug(f"Сохранены Telegram file_id для {pdf_path}")
    except Exception as e:
        logger.error(f"Ошибка сохранения file_id для {pdf_path}: {e}")

def load_telegram_file_ids(pdf_path: str) -> dict[int, str]:
    """Загрузить Telegram file_id для страниц PDF"""
    try:
        file_ids_path = get_telegram_file_ids_path(pdf_path)
        if file_ids_path.exists():
            with open(file_ids_path, 'r', encoding='utf-8') as f:
                file_ids = json.load(f)
                # Конвертируем ключи из строк в int
                return {int(k): v for k, v in file_ids.items()}
    except Exception as e:
        logger.debug(f"Не удалось загрузить file_id для {pdf_path}: {e}")
    return {}

def get_telegram_document_file_id_path(pdf_path: str) -> Path:
    """Получить путь к файлу с Telegram file_id для PDF документа"""
    cache_dir = get_cache_path(pdf_path)
    return cache_dir / "telegram_document_file_id.json"

def save_telegram_document_file_id(pdf_path: str, file_id: str):
    """Сохранить Telegram file_id для PDF документа"""
    try:
        file_id_path = get_telegram_document_file_id_path(pdf_path)
        file_id_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_id_path, 'w', encoding='utf-8') as f:
            json.dump({'file_id': file_id}, f, ensure_ascii=False, indent=2)
        logger.debug(f"Сохранен Telegram file_id документа для {pdf_path}")
    except Exception as e:
        logger.error(f"Ошибка сохранения file_id документа для {pdf_path}: {e}")

def load_telegram_document_file_id(pdf_path: str) -> Optional[str]:
    """Загрузить Telegram file_id для PDF документа"""
    try:
        file_id_path = get_telegram_document_file_id_path(pdf_path)
        if file_id_path.exists():
            with open(file_id_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('file_id')
    except Exception as e:
        logger.debug(f"Не удалось загрузить file_id документа для {pdf_path}: {e}")
    return None

def clear_cache(pdf_path: str = None):
    """Очистить кэш для конкретного PDF или весь кэш"""
    if pdf_path:
        cache_dir = get_cache_path(pdf_path)
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            logger.info(f"Кэш очищен для {pdf_path}")
    else:
        # Очищаем весь кэш
        if os.path.exists(CACHE_PATH):
            import shutil
            for item in os.listdir(CACHE_PATH):
                item_path = os.path.join(CACHE_PATH, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            logger.info("Весь кэш очищен")

async def recache_pdf(pdf_path: str) -> bool:
    """
    Пересоздать кэш для конкретного PDF файла
    
    Args:
        pdf_path: Путь к PDF файлу
        
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        # Очищаем старый кэш
        clear_cache(pdf_path)
        
        # Создаем новый кэш
        await pdf_to_images(pdf_path)
        logger.info(f"Кэш пересоздан для {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при пересоздании кэша для {pdf_path}: {e}")
        return False

async def pre_cache_all_pdfs(menu_path: str) -> dict:
    """
    Предварительное кэширование всех PDF файлов в меню
    
    Args:
        menu_path: Путь к папке с меню
        
    Returns:
        dict: Статистика кэширования {'total': int, 'cached': int, 'errors': int}
    """
    from config import MENU_PATH
    
    stats = {'total': 0, 'cached': 0, 'errors': 0}
    pdf_files = []
    
    # Собираем все PDF файлы
    if not os.path.exists(menu_path):
        logger.warning(f"Папка меню не найдена: {menu_path}")
        return stats
    
    for root, dirs, files in os.walk(menu_path):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                pdf_files.append(pdf_path)
                stats['total'] += 1
    
    logger.info(f"Найдено {stats['total']} PDF файлов для предварительного кэширования")
    
    # Кэшируем каждый PDF
    for pdf_path in pdf_files:
        try:
            cache_dir = get_cache_path(pdf_path)
            # Проверяем, есть ли уже кэш (поддерживаем как PNG, так и JPEG)
            jpeg_files = list(cache_dir.glob("*.jpg"))
            png_files = list(cache_dir.glob("*.png"))
            if cache_dir.exists() and (jpeg_files or png_files):
                stats['cached'] += 1
                logger.debug(f"Кэш уже существует для {pdf_path}")
            else:
                # Конвертируем PDF
                await pdf_to_images(pdf_path)
                stats['cached'] += 1
                logger.info(f"Предварительно закеширован: {pdf_path}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Ошибка при кэшировании {pdf_path}: {e}")
    
    logger.info(f"Предварительное кэширование завершено: {stats['cached']}/{stats['total']} успешно, {stats['errors']} ошибок")
    return stats
