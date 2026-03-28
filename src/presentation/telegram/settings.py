from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelegramSettings:
    admin_telegram_id: int | None


@dataclass(frozen=True, slots=True)
class TelegramRuntimeSettings:
    bot_token: str
    admin_telegram_id: int | None
    redis_url: str
    selenium_headless: bool
    selenium_wait_seconds: int
    timezone_name: str
    proactive_notification_cooldown_days: int
    matches_lookahead_days: int
    rates_parser_batch_pause_seconds: float
    rates_parser_retry_count: int
    rates_parser_retry_pause_seconds: float


def load_telegram_settings() -> TelegramSettings:
    raw_admin_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    admin_telegram_id: int | None = None
    if raw_admin_id:
        try:
            admin_telegram_id = int(raw_admin_id)
        except ValueError:
            admin_telegram_id = None
    return TelegramSettings(admin_telegram_id=admin_telegram_id)


def load_telegram_runtime_settings() -> TelegramRuntimeSettings:
    telegram_settings = load_telegram_settings()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        raise ValueError("REDIS_URL is required for aiogram Redis FSM storage")

    selenium_headless = os.getenv("SELENIUM_VISIBLE", "").strip().lower() not in {"1", "true", "yes"}
    selenium_wait_seconds = int(os.getenv("SELENIUM_WAIT_SECONDS", "20"))
    timezone_name = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
    proactive_notification_cooldown_days = max(0, int(os.getenv("PROACTIVE_NOTIFICATION_COOLDOWN_DAYS", "7")))
    matches_lookahead_days = max(1, int(os.getenv("MATCHES_LOOKAHEAD_DAYS", "90")))
    rates_parser_batch_pause_seconds = max(0.0, float(os.getenv("RATES_PARSER_BATCH_PAUSE_SECONDS", "3")))
    rates_parser_retry_count = max(0, int(os.getenv("RATES_PARSER_RETRY_COUNT", "1")))
    rates_parser_retry_pause_seconds = max(0.0, float(os.getenv("RATES_PARSER_RETRY_PAUSE_SECONDS", "1")))

    return TelegramRuntimeSettings(
        bot_token=token,
        admin_telegram_id=telegram_settings.admin_telegram_id,
        redis_url=redis_url,
        selenium_headless=selenium_headless,
        selenium_wait_seconds=selenium_wait_seconds,
        timezone_name=timezone_name,
        proactive_notification_cooldown_days=proactive_notification_cooldown_days,
        matches_lookahead_days=matches_lookahead_days,
        rates_parser_batch_pause_seconds=rates_parser_batch_pause_seconds,
        rates_parser_retry_count=rates_parser_retry_count,
        rates_parser_retry_pause_seconds=rates_parser_retry_pause_seconds,
    )
