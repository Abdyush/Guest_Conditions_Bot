from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelegramSettings:
    admin_telegram_id: int | None


def load_telegram_settings() -> TelegramSettings:
    raw_admin_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    admin_telegram_id: int | None = None
    if raw_admin_id:
        try:
            admin_telegram_id = int(raw_admin_id)
        except ValueError:
            admin_telegram_id = None
    return TelegramSettings(admin_telegram_id=admin_telegram_id)
