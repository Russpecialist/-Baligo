"""Генерация клавиатур для бота"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional, Dict


def get_main_menu_keyboard(role: str, has_restaurants: bool = False) -> ReplyKeyboardMarkup:
    """Генерация главного меню в зависимости от роли"""
    if role == 'admin':
        buttons = [
            [KeyboardButton(text="🚶 Вернуться в меню пользователя")],
            [KeyboardButton(text="✅ Разбанить пользователя"),
             KeyboardButton(text="⛔ Забанить пользователя")],
            [KeyboardButton(text="⭐ Добавить админа"),
             KeyboardButton(text="❌ Удалить админа")],
            [KeyboardButton(text="➕ Добавить ресторан"),
             KeyboardButton(text="✏️ Изменить ресторан")],
            [KeyboardButton(text="✉ Отправить рассылку")],
            [KeyboardButton(text="📋 Запросы на согласование")]
        ]
        # Если у админа есть рестораны, добавляем кнопку личного кабинета
        if has_restaurants:
            buttons.append([KeyboardButton(text="🏢 Личный кабинет ресторана")])
    elif role == 'restaurant':
        buttons = [
            [KeyboardButton(text="🏢 Личный кабинет ресторана")],
            [KeyboardButton(text="🏪 Просмотр всех ресторанов")]
        ]
    else:  # user
        buttons = [
            [KeyboardButton(text="🌴 Выбрать район")],
            [KeyboardButton(text="🤖 AI-ассистент")],
            [KeyboardButton(text="🏠 Вернуться в главное меню")]

        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_categories_keyboard(categories: List[str]) -> ReplyKeyboardMarkup:
    """Клавиатура выбора категории партнёров"""
    buttons = [[KeyboardButton(text=cat)] for cat in categories]
    buttons.append([KeyboardButton(text="⬅️ Назад к районам")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_regions_keyboard(regions: List[str], is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = []
    if is_admin:
        buttons.append([KeyboardButton(text="🔐 Вернуться в админское меню")])
    else:
        buttons.append([KeyboardButton(text="🏠 Вернуться в главное меню")])

    for region in regions:
        buttons.append([KeyboardButton(text=region)])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurants_keyboard(restaurants: List[str], show_banquet: bool = True) -> ReplyKeyboardMarkup:
    """Генерация клавиатуры с ресторанами (2 ресторана в ряд)"""
    buttons = []

    # Добавляем рестораны по 2 в ряд
    for i in range(0, len(restaurants), 2):
        row = [KeyboardButton(text=restaurants[i])]
        if i + 1 < len(restaurants):
            row.append(KeyboardButton(text=restaurants[i + 1]))
        buttons.append(row)

    # Кнопка "Вернуться в главное меню" занимает 2 ряда (широкая кнопка)
    buttons.append([KeyboardButton(text="🏠 Вернуться в главное меню")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurant_info_keyboard() -> ReplyKeyboardMarkup:
    """Генерация клавиатуры для информации о ресторане"""
    buttons = [
        [KeyboardButton(text="📋 Меню")],
        [KeyboardButton(text="🎁 Спец. предложения/Коллаборации")],
        [KeyboardButton(text="🎊 События")],
        [KeyboardButton(text="🎉 Заказать банкет")],
        [KeyboardButton(text="📍 Адрес")],
        [KeyboardButton(text="🚚 Доставка")],
        [KeyboardButton(text="⬅️ Назад к ресторанам региона")],
        [KeyboardButton(text='🏠 Вернуться в главное меню')]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurant_cabinet_keyboard() -> ReplyKeyboardMarkup:
    """Генерация клавиатуры личного кабинета ресторана"""
    buttons = [
        [KeyboardButton(text="📝 Редактировать информацию")],
        [KeyboardButton(text="📋 Изменить меню"),
         KeyboardButton(text="🎉 Изменить банкет")],
        [KeyboardButton(text="🎁 Изменить Акции"),
         KeyboardButton(text="🎊 Изменить События")],
        [KeyboardButton(text="📊 Статус заявок")],
        [KeyboardButton(text="👁 Просмотр информации")],
        [KeyboardButton(text="➕ Добавить модератора"),
         KeyboardButton(text="➖ Удалить модератора")],
        [KeyboardButton(text="🏠 Вернуться в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_edit_fields_keyboard() -> ReplyKeyboardMarkup:
    """Генерация клавиатуры для выбора поля редактирования"""
    buttons = [
        [KeyboardButton(text="Название ресторана")],
        [KeyboardButton(text="Меню")],
        [KeyboardButton(text="Бронирование")],
        [KeyboardButton(text="Доставка")],
        [KeyboardButton(text="Регион")],
        [KeyboardButton(text="Адрес")],
        [KeyboardButton(text="⬅️ Назад в кабинет")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    """Генерация inline клавиатуры для согласования"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Подтвердить",
                                 callback_data=f"approve_{approval_id}"),
            InlineKeyboardButton(text="❌ Отклонить",
                                 callback_data=f"reject_{approval_id}")
        ],
        [
            InlineKeyboardButton(text="📋 Просмотреть изменения",
                                 callback_data=f"view_{approval_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_promotion_event_approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    """Генерация inline клавиатуры для согласования акций и событий"""
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Одобрить", callback_data=f"pe_approve_{approval_id}"),
            InlineKeyboardButton(text="❌ Отклонить",
                                 callback_data=f"pe_reject_{approval_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_show_approvals_keyboard() -> InlineKeyboardMarkup:
    """Генерация inline клавиатуры с кнопкой 'Показать' для уведомления о новых заявках"""
    buttons = [
        [
            InlineKeyboardButton(text="📋 Показать заявки",
                                 callback_data="show_approvals")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_cabinet_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для возврата в кабинет"""
    buttons = [
        [KeyboardButton(text="⬅️ Назад в кабинет")],
        [KeyboardButton(text="🏠 Вернуться в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    buttons = [
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_skip_photo_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопками 'Пропустить' и 'Отменить' для загрузки фото"""
    buttons = [
        [KeyboardButton(text="⏭ Пропустить")],
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurant_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для подтверждения создания ресторана"""
    buttons = [
        [KeyboardButton(text="✅ Добавить"), KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurants_list_keyboard(restaurants: List[str]) -> ReplyKeyboardMarkup:
    """Клавиатура со списком ресторанов для выбора"""
    buttons = []
    for restaurant in restaurants:
        buttons.append([KeyboardButton(text=restaurant)])
    buttons.append([KeyboardButton(text="❌ Отменить")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_restaurant_edit_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для редактирования ресторана"""
    buttons = [
        [KeyboardButton(text="📄 Изменить меню")],
        [KeyboardButton(text="❌ Отменить")],
        [KeyboardButton(text="🗑️ Удалить ресторан")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_delete_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для подтверждения удаления"""
    buttons = [
        [KeyboardButton(text="✅ Да, удалить"),
         KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_approval_newsletter_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора действия с рассылкой после согласования"""
    buttons = [
        [KeyboardButton(text="✉ Отправить рассылку")],
        [KeyboardButton(text="✏️ Изменить рассылку")],
        [KeyboardButton(text="❌ Не отправлять рассылку")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_newsletter_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для подтверждения отправки рассылки"""
    buttons = [
        [KeyboardButton(text="✅ Отправить рассылку")],
        [KeyboardButton(text="⬅️ Вернуться назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_promotions_list_keyboard(items: List[Dict], current_page: int = 0, items_per_page: int = 5, item_type: str = 'promotion') -> InlineKeyboardMarkup:
    """Генерация inline клавиатуры для списка акций или событий с пагинацией"""
    from aiogram.types import InlineKeyboardButton

    total_items = len(items)
    total_pages = (total_items + items_per_page -
                   1) // items_per_page if total_items > 0 else 1

    buttons = []

    # Показываем элементы текущей страницы
    start_idx = current_page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)

    for i in range(start_idx, end_idx):
        item = items[i]
        title = item.get('title', f'Элемент {i+1}')[:30]  # Ограничиваем длину
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {title}",
                callback_data=f"{item_type}_edit_{item['id']}"
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ Удалить {title[:25]}",
                callback_data=f"{item_type}_delete_{item['id']}"
            )
        ])

    # Кнопки навигации
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад", callback_data=f"{item_type}_page_{current_page - 1}"))
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️", callback_data=f"{item_type}_page_{current_page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка "Новое событие/акция"
    buttons.append([
        InlineKeyboardButton(
            text=f"➕ Новое {'событие' if item_type == 'event' else 'акция'}",
            callback_data=f"{item_type}_new"
        )
    ])

    # Кнопка "Назад в кабинет"
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад в кабинет",
                             callback_data=f"{item_type}_back")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_promotion_event_edit_keyboard(item_id: int, item_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования акции или события"""
    from aiogram.types import InlineKeyboardButton

    buttons = [
        [
            InlineKeyboardButton(text="✏️ Изменить",
                                 callback_data=f"{item_type}_edit_{item_id}"),
            InlineKeyboardButton(
                text="🗑️ Удалить", callback_data=f"{item_type}_delete_{item_id}")
        ],
        [InlineKeyboardButton(text="⬅️ Назад к списку",
                              callback_data=f"{item_type}_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_promotion_event_view_keyboard(current_index: int, total_count: int, item_type: str) -> InlineKeyboardMarkup:
    """Генерация inline клавиатуры для просмотра акций/событий с навигацией"""
    from aiogram.types import InlineKeyboardButton

    buttons = []

    # Если записей больше одной, показываем кнопки навигации
    if total_count > 1:
        nav_buttons = []

        # Кнопка "Назад" - показываем, если не на первой записи
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"view_{item_type}_prev_{current_index}"))

        # Кнопка "Вперед" - показываем, если не на последней записи
        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="Вперед ➡️", callback_data=f"view_{item_type}_next_{current_index}"))

        if nav_buttons:
            buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
