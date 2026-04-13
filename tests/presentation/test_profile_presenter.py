from __future__ import annotations

from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import Occupancy
from src.domain.value_objects.money import Money
from src.presentation.telegram.presenters.profile_presenter import render_profile


def test_render_profile_hides_children_lines_when_counts_are_zero() -> None:
    profile = GuestPreferences(
        desired_price_per_night=Money.rub(700000),
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
        guest_name="Никита",
    )

    rendered = render_profile(profile)

    assert "Дети, от 4 до 17 лет:" not in rendered
    assert "Дети, до 3 лет:" not in rendered


def test_render_profile_uses_new_children_labels() -> None:
    profile = GuestPreferences(
        desired_price_per_night=Money.rub(700000),
        occupancy=Occupancy(adults=2, children_4_13=2, infants=1),
        guest_name="Никита",
    )

    rendered = render_profile(profile)

    assert "Дети, от 4 до 17 лет: 2" in rendered
    assert "Дети, до 3 лет: 1" in rendered


def test_render_profile_uses_new_budget_label() -> None:
    profile = GuestPreferences(
        desired_price_per_night=Money.rub(700000),
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
        guest_name="Никита",
    )

    rendered = render_profile(profile)

    assert "Целевой бюджет в сутки" in rendered
    assert "700 000 ₽" in rendered
    assert "700 000 ₽ за сутки" not in rendered
