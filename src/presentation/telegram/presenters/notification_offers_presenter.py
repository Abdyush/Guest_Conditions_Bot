from __future__ import annotations

from src.presentation.telegram.presenters.available_presenter import render_available_offer_text


def render_notification_intro(*, guest_name: str) -> str:
    short_name = _short_guest_name(guest_name)
    return f"Я нашёл для Вас новые подходящие предложения ✨\n{short_name}, ниже откроется просмотр доступных вариантов и цен."


def render_notification_groups_prompt() -> str:
    return "Выберите группу категорий, чтобы посмотреть доступные варианты и цены."


def render_notification_categories_prompt(*, group_label: str) -> str:
    return f"{group_label}\n\nВыберите категорию."


def render_notification_flow_hint() -> str:
    return "Сейчас открыт сценарий новых предложений. Используйте кнопки этого сценария и кнопку «Главное меню»."


def render_notification_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    return render_available_offer_text(offer_title=offer_title, offer_text=offer_text)


def _short_guest_name(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return "Гость"
    return normalized.split()[0]
