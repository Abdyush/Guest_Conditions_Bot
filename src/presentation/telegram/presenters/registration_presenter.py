from __future__ import annotations

from decimal import Decimal

from src.presentation.telegram.state.session_store import RegistrationDraft
from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, CATEGORY_LABEL_TO_CODE


def render_welcome_message() -> str:
    return (
        "Добро пожаловать! ✨\n"
        "Я помогу подобрать для Вас лучшие цены на номера и виллы, а также сообщу, "
        "когда появятся особенно выгодные предложения.\n"
        "Чтобы начать, пожалуйста, подтвердите номер телефона."
    )


def render_phone_reminder() -> str:
    return "Пожалуйста, подтвердите номер телефона кнопкой «Поделиться номером телефона» ниже."


def render_registration_intro() -> str:
    return (
        "Номер не найден в системе.\n"
        "Давайте создадим Ваш профиль — это займет меньше минуты."
    )


def render_adults_prompt() -> str:
    return (
        "Сколько взрослых будет проживать?\n"
        "Введите целое число, например: 1 или 2."
    )


def render_children_prompt() -> str:
    return (
        "Сколько детей от 4 до 13 лет будет проживать?\n"
        "Если детей нет — отправьте 0."
    )


def render_infants_prompt() -> str:
    return (
        "Сколько детей до 3 лет будет проживать?\n"
        "Если детей нет — отправьте 0."
    )


def render_categories_prompt(*, selected_codes: set[str] | None = None) -> str:
    selected_labels = _format_categories(selected_codes or set())
    return (
        "Какие категории номеров Вам особенно интересны? 🏡\n"
        "Можно выбрать несколько вариантов.\n"
        "После выбора нажмите «Готово».\n\n"
        f"Сейчас выбрано: {selected_labels}"
    )


def render_loyalty_prompt() -> str:
    return (
        "Есть ли у Вас статус в программе лояльности?\n"
        "Если статус есть — выберите его из списка.\n"
        "Если нет — выберите вариант «Без статуса»."
    )


def render_bank_prompt() -> str:
    return (
        "Есть ли у Вас статус в программе Сбера?\n"
        "Если статус есть — выберите его из списка.\n"
        "Если нет — выберите вариант «Без статуса»."
    )


def render_price_prompt() -> str:
    return (
        "Укажите желаемую цену за ночь 💳\n"
        "Когда стоимость будет ниже этого значения, я отправлю Вам уведомление.\n"
        "Введите сумму в рублях, например: 70000."
    )


def render_adults_invalid() -> str:
    return "Пожалуйста, введите целое число от 1 и выше. Например: 1 или 2."


def render_children_invalid() -> str:
    return "Пожалуйста, введите целое число от 0 и выше. Например: 0, 1 или 2."


def render_infants_invalid() -> str:
    return "Пожалуйста, введите целое число от 0 и выше. Например: 0 или 1."


def render_groups_use_buttons() -> str:
    return "Пожалуйста, используйте кнопки ниже для выбора категорий. Когда закончите, нажмите «Готово»."


def render_select_at_least_one() -> str:
    return "Пожалуйста, выберите хотя бы одну категорию, чтобы продолжить."


def render_loyalty_invalid() -> str:
    return "Пожалуйста, выберите статус кнопкой ниже."


def render_bank_invalid() -> str:
    return "Пожалуйста, выберите статус кнопкой ниже."


def render_price_invalid() -> str:
    return "Пожалуйста, укажите сумму в рублях, например: 70000."


def render_registration_summary(reg: RegistrationDraft) -> str:
    guest_name = (reg.name or "Гость").strip() or "Гость"
    loyalty = _format_loyalty(reg.loyalty_status, reg.bank_status)
    bank = _format_bank(reg.bank_status)
    desired_price = _format_price(reg.desired_price_rub)
    return (
        "Проверьте, пожалуйста, данные профиля:\n\n"
        f"Имя: {guest_name}\n"
        f"Взрослых: {reg.adults or 0}\n"
        f"Детей 4–13: {reg.children_4_13 or 0}\n"
        f"Детей до 3: {reg.infants_0_3 or 0}\n"
        f"Категории: {_format_categories(reg.allowed_groups or set())}\n"
        f"Статус программы лояльности: {loyalty}\n"
        f"Статус в Сбере: {bank}\n"
        f"Желаемая цена: {desired_price}"
    )


def render_registration_done() -> str:
    return (
        "Регистрация завершена ✅\n"
        "Теперь я буду автоматически подбирать для Вас подходящие категории и периоды проживания.\n"
        "Когда появятся предложения, соответствующие Вашим условиям, или особенно выгодные цены — "
        "я сразу отправлю уведомление."
    )


def _format_categories(selected_codes: set[str]) -> str:
    if not selected_codes:
        return "—"
    code_to_label = {code: label for label, code in CATEGORY_LABEL_TO_CODE.items()}
    labels = [code_to_label.get(code, code) for code in sorted(selected_codes)]
    return ", ".join(labels)


def _format_loyalty(loyalty_status: str | None, bank_status: str | None) -> str:
    if bank_status:
        return "Не применяется при статусе Сбера"
    if not loyalty_status or loyalty_status.lower() == "white":
        return "Без статуса"
    return loyalty_status


def _format_bank(bank_status: str | None) -> str:
    if not bank_status:
        return "Без статуса"
    for label, code in BANK_LABEL_TO_CODE.items():
        if code == bank_status:
            return label
    return bank_status


def _format_price(value: Decimal | None) -> str:
    if value is None:
        return "—"
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return f"{int(normalized)} ₽"
    return f"{normalized} ₽"
