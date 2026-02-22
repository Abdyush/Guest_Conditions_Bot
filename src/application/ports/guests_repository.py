from __future__ import annotations

from typing import Protocol

from src.domain.entities.guest_preferences import GuestPreferences


class GuestsRepository(Protocol):
    def get_active_guests(self) -> list[GuestPreferences]:
        ...
