import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла (если есть)
load_dotenv()
# Telegram Bot Token
token_id = os.getenv('BOT_TOKEN')

# PostgreSQL Database Configuration
namedb = os.getenv('POSTGRES_DB', 'restobot_db')
user = os.getenv('POSTGRES_USER', 'restobot_user')
password = os.getenv('POSTGRES_PASSWORD', 'your_secure_password')
host = os.getenv('POSTGRES_HOST', 'localhost')
port = os.getenv('POSTGRES_PORT', '5432')

# Google Sheets Configuration
spreadsheet_key = os.getenv('SPREADSHEET_KEY')

# Список таблиц для синхронизации с Google Sheets
table_names = [
    "users",
    "log_users", 
    "restaurant"
    # Добавьте другие таблицы по необходимости
]

# Дополнительные настройки
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '2'))

# Проверка обязательных переменных
if not token_id:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

if not spreadsheet_key:
    raise ValueError("SPREADSHEET_KEY не установлен в переменных окружения")

# Пути к файлам (для Docker)
MENU_PATH = os.getenv('MENU_PATH', '/app/rest_menu')
LOGS_PATH = os.getenv('LOGS_PATH', '/app/logs')
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', '/app/client_secret.json')
CACHE_PATH = os.getenv('CACHE_PATH', '/app/cache')

# Временная папка для файлов, ожидающих согласования
# По умолчанию используем папку рядом с rest_menu для удобства разработки вне Docker
_pending_menu_default = os.path.join(os.path.dirname(MENU_PATH) if os.path.dirname(MENU_PATH) else '.', 'pending_menu')
PENDING_MENU_PATH = os.getenv('PENDING_MENU_PATH', _pending_menu_default)

# Создаем папку pending_menu, если её нет
os.makedirs(PENDING_MENU_PATH, exist_ok=True)

# Функция для получения безопасного пути в rest_menu
def get_safe_menu_path(relative_path=""):
    """Получить безопасный путь в директории меню"""
    import os.path
    base_path = MENU_PATH
    if relative_path:
        # Убираем потенциально опасные элементы пути
        safe_path = os.path.normpath(relative_path).lstrip('/')
        full_path = os.path.join(base_path, safe_path)
        # Проверяем, что путь находится внутри базовой директории
        if os.path.commonpath([base_path, full_path]) == base_path:
            return full_path
    return base_path