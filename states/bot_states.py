"""FSM состояния для бота"""
from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    # Общие состояния
    waiting_region = State()
    waiting_category = State()        # выбор категории партнёров
    waiting_restaurant = State()
    waiting_banquet_restaurant = State()
    waiting_menu_action = State()
    waiting_menu_item = State()
    
    # Админ состояния
    waiting_admin_action = State()
    waiting_username = State()
    waiting_newsletter = State()
    waiting_newsletter_confirm = State()
    waiting_file_manager_action = State()
    waiting_file_upload = State()
    
    # Состояния для добавления ресторана
    waiting_restaurant_name = State()
    waiting_restaurant_address = State()
    waiting_restaurant_reservation = State()
    waiting_restaurant_delivery = State()
    waiting_restaurant_region = State()
    waiting_restaurant_category = State()     # выбор категории при создании партнёра
    waiting_restaurant_username = State()
    waiting_restaurant_confirm = State()
    
    # Состояния для изменения ресторана
    waiting_restaurant_edit_selection = State()
    waiting_restaurant_edit_all = State()
    waiting_restaurant_delete_confirm = State()
    
    # Ресторан состояния
    waiting_restaurant_cabinet = State()
    waiting_restaurant_edit_field = State()
    waiting_restaurant_edit_value = State()
    waiting_restaurant_menu_upload = State()
    waiting_restaurant_selection = State()  # Выбор ресторана для редактирования
    waiting_restaurant_menu_manager = State()  # Управление меню ресторана
    waiting_restaurant_banquet_manager = State()  # Управление банкетами ресторана
    waiting_restaurant_banquet_upload = State()  # Загрузка банкетного файла
    waiting_moderator_restaurant_selection = State()  # Выбор ресторана для управления модераторами
    waiting_moderator_username = State()  # Ввод username модератора для добавления
    waiting_moderator_remove_selection = State()  # Выбор модератора для удаления
    
    # Состояния для рассылки после согласования
    waiting_approval_newsletter = State()  # Выбор действия с рассылкой
    waiting_approval_newsletter_edit = State()  # Редактирование текста рассылки
    waiting_approval_newsletter_confirm = State()  # Подтверждение отправки рассылки
    
    # Состояния для управления акциями и событиями
    waiting_promotions_list = State()  # Просмотр списка акций
    waiting_events_list = State()  # Просмотр списка событий
    waiting_promotion_title = State()  # Ввод названия акции
    waiting_promotion_description = State()  # Ввод описания акции
    waiting_promotion_photo = State()  # Загрузка фото акции
    waiting_event_title = State()  # Ввод названия события
    waiting_event_description = State()  # Ввод описания события
    waiting_event_photo = State()  # Загрузка фото события
    
    # Состояния для просмотра акций и событий пользователями
    viewing_promotions = State()  # Просмотр акций
    viewing_events = State()  # Просмотр событий