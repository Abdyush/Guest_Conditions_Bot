from __future__ import annotations


BUTTONS = {
    "best_period": "📉 Самый выгодный период",
    "period_quotes": "📅 Цены на период",
    "available_rooms": "🏨 Мои доступные категории",
    "edit_data": "⚙️ Редактировать данные",

    "back": "⬅️ Назад",
    "main_menu": "🏠 Главное меню",
    "cancel": "❌ Отмена",

    "share_phone": "📱 Поделиться номером",
    "groups_done": "✅ Готово",

    "edit_adults": "🧑 Взрослые",
    "edit_children": "👶 Дети 4–13",
    "edit_infants": "🍼 Дети до 3",

    "edit_groups": "❤️ Любимые категории",
    "edit_loyalty": "⭐ Лояльность",
    "edit_bank": "🏦 Сбер статус",
    "edit_price": "💰 Желаемая цена",
}

CATEGORY_LABEL_TO_CODE = {
    "Делюкс": "DELUXE",
    "Делюкс новые номера": "DELUXE NEW",
    "Люкс": "SUITE",
    "Апартаменты СПА": "SPA MEDICAL SUITE",
    "Королевский люкс": "ROYAL SUITE",
    "Пентхаус": "PENTHOUSE",
    "Апартаменты в Японском Саду «Имение Сёгуна»": "JAPANESE SUITE GARDEN",
    "Вилла": "VILLA",
}

LOYALTY_OPTIONS = ["White", "Bronze", "Silver", "Gold", "Platinum", "Diamond"]

BANK_LABEL_TO_CODE = {
    "Нет статуса": "",
    "СберПремьер": "SBER_PREMIER",
    "СберПервый": "SBER_FIRST",
    "СберПрайват": "SBER_PRIVATE",
}

MESSAGES = {
    "binding_found": "Привязка найдена: guest_id={guest_id}.",
    "ask_phone": "Чтобы авторизоваться, нажмите 'Поделиться номером'.",
    "unlink_done": "Привязка удалена. Нажмите /start и авторизуйтесь снова по номеру.",
    "send_own_phone": "Нужно отправить именно ваш номер.",
    "auth_done": "Авторизация выполнена: guest_id={guest_id}.",
    "registration_start": "Номер не найден. Начнем регистрацию.\nКоличество взрослых (целое число, минимум 1):",
    "cancelled": "Отменено.",
    "phone_only": "Для авторизации отправьте номер кнопкой 'Поделиться номером'.",
    "ask_best_group": "Выберите категорию кнопкой:",
    "ask_quotes_group": "Выберите категорию для расчета цен на период:",
    "ask_quotes_calendar": "Выберите период: сначала дата заезда, затем дата выезда.",
    "quotes_use_calendar": "Используйте календарь кнопками ниже.",
    "menu_hint": "Выберите действие кнопками меню.",
    "send_phone_first": "Сначала отправьте номер.",
    "reg_adults_invalid": "Введите корректное число взрослых (>=1):",
    "reg_step_2": "Количество взрослых (целое число, минимум 1):",
    "reg_step_3": "Количество детей от 4 до 13 лет (0+):",
    "reg_children_invalid": "Введите корректное количество детей 4-13 (0+):",
    "reg_step_4": "Количество детей до 3 лет (0+):",
    "reg_infants_invalid": "Введите корректное количество детей 0-3 (0+):",
    "reg_step_5": "Выберите любимые категории (можно несколько), затем нажмите 'Готово'.",
    "reg_groups_use_buttons": "Используйте кнопки ниже для выбора категорий.",
    "reg_select_at_least_one": "Выберите минимум одну категорию.",
    "reg_step_6": "Выберите статус программы лояльности:",
    "reg_loyalty_invalid": "Выберите статус кнопкой.",
    "reg_step_7": "Выберите статус в Сбере:",
    "reg_bank_invalid": "Выберите статус кнопкой.",
    "reg_step_8": "Желаемая цена за сутки в рублях (например, 70000):",
    "reg_price_invalid": "Введите корректную цену в рублях, число больше 0:",
    "registration_failed": "Не удалось завершить регистрацию. Попробуйте позже.",
    "registration_done": "Регистрация завершена. Ваш guest_id={guest_id}.",
    "auth_required": "Сначала авторизуйтесь по номеру.",
    "best_period_failed": "Не удалось получить периоды. Попробуйте позже.",
    "period_quotes_failed": "Не удалось получить цены. Попробуйте позже.",
    "profile_not_found": "Профиль гостя не найден.",
    "available_none": "Нет доступных вариантов по вашим критериям.",
    "available_pick_category": "Выберите категорию, чтобы посмотреть периоды и цены:",
    "edit_pick_field": "Выберите, что хотите изменить:",
    "edit_saved": "Изменения сохранены.",
}


def msg(key: str, **kwargs: str) -> str:
    return MESSAGES[key].format(**kwargs)
