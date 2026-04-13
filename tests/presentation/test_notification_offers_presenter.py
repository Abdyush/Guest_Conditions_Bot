from __future__ import annotations

from src.presentation.telegram.presenters.notification_offers_presenter import render_notification_intro


def test_render_notification_intro_uses_only_first_name() -> None:
    rendered = render_notification_intro(guest_name="Никита Абдюшев")

    assert "Никита," in rendered
    assert "Абдюшев" not in rendered
