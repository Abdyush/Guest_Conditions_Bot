from __future__ import annotations

from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.presentation.telegram.mappers.value_parser import telegram_profile_name
from src.presentation.telegram.ui_texts import CATEGORY_LABEL_TO_CODE


LOYALTY_EMOJI = {
    LoyaltyStatus.WHITE: "⚪",
    LoyaltyStatus.BRONZE: "🥉",
    LoyaltyStatus.SILVER: "🥈",
    LoyaltyStatus.GOLD: "🥇",
    LoyaltyStatus.PLATINUM: "💎",
    LoyaltyStatus.DIAMOND: "🔷",
}

SBER_LEVEL_LABELS = {
    BankStatus.SBER_PREMIER: "СберПремьер",
    BankStatus.SBER_FIRST: "СберПервый",
    BankStatus.SBER_PRIVATE: "СберПрайват",
}


def render_profile(profile: GuestPreferences, user=None) -> str:
    code_to_label = {v: k for k, v in CATEGORY_LABEL_TO_CODE.items()}
    groups = sorted(profile.effective_allowed_groups or set())
    categories_list = "\n".join(f"• {code_to_label.get(group, group)}" for group in groups) if groups else "• —"
    full_name = _format_full_name(profile=profile, user=user)
    adults_text = _format_adults(profile.occupancy.adults)
    children_block = _format_children_block(profile)
    status_line = _format_status_line(profile)
    price_formatted = _format_price(profile.desired_price_per_night.round_rubles())

    guest_lines = [adults_text]
    if children_block:
        guest_lines.append(children_block)

    return (
        "Ваши данные\n\n"
        f"👤 {full_name}\n\n"
        "👥 Состав гостей\n"
        f"{'\n'.join(guest_lines)}\n\n"
        "🏨 Выбранные категории\n"
        f"{categories_list}\n\n"
        "💎 Статус\n"
        f"{status_line}\n\n"
        "💰 Целевой бюджет в сутки\n"
        f"{price_formatted} ₽"
    )


def _format_full_name(profile: GuestPreferences, user) -> str:
    if user is not None:
        full_name = telegram_profile_name(user).strip()
        if full_name and full_name != "Guest":
            return full_name
    guest_name = (profile.guest_name or "").strip()
    return guest_name or "Гость"


def _format_adults(adults: int) -> str:
    if adults == 1:
        return "1 взрослый"
    return f"{adults} взрослых"


def _format_children_block(profile: GuestPreferences) -> str:
    lines: list[str] = []
    if profile.occupancy.children_4_13 > 0:
        lines.append(f"Дети, от 4 до 17 лет: {profile.occupancy.children_4_13}")
    if profile.occupancy.infants > 0:
        lines.append(f"Дети, до 3 лет: {profile.occupancy.infants}")
    return "\n".join(lines)


def _format_status_line(profile: GuestPreferences) -> str:
    if profile.bank_status is not None:
        sber_level = SBER_LEVEL_LABELS.get(profile.bank_status)
        if sber_level:
            return f"🏦 {sber_level}"
        return "🏦 Сбер: подключён"

    loyalty_status = profile.loyalty_status or LoyaltyStatus.WHITE
    loyalty_label = loyalty_status.value.capitalize()
    loyalty_emoji = LOYALTY_EMOJI[loyalty_status]
    return f"{loyalty_emoji} {loyalty_label}"


def _format_price(value: int) -> str:
    return f"{value:,}".replace(",", " ")
