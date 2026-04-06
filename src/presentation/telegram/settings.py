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
    use_travelline_rates_source: bool
    travelline_compare_only: bool
    travelline_enable_publish: bool
    travelline_fallback_to_selenium: bool
    travelline_hotel_code: str
    travelline_base_url: str
    travelline_timeout_seconds: float
    travelline_publish_max_tariff_pairing_anomalies: int
    travelline_publish_max_unmapped_categories: int


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    use_travelline_rates_source = _parse_bool_env("USE_TRAVELLINE_RATES_SOURCE", True)
    travelline_compare_only = _parse_bool_env("TRAVELLINE_COMPARE_ONLY", False)
    travelline_enable_publish = _parse_bool_env("TRAVELLINE_ENABLE_PUBLISH", True)
    travelline_fallback_to_selenium = _parse_bool_env("TRAVELLINE_FALLBACK_TO_SELENIUM", True)
    travelline_hotel_code = os.getenv("TRAVELLINE_HOTEL_CODE", "").strip()
    travelline_base_url = os.getenv(
        "TRAVELLINE_BASE_URL",
        "https://ru-ibe.tlintegration.ru/ApiWebDistribution/BookingForm",
    ).strip()
    travelline_timeout_seconds = max(1.0, float(os.getenv("TRAVELLINE_TIMEOUT_SECONDS", "20")))
    travelline_publish_max_tariff_pairing_anomalies = max(
        0,
        int(os.getenv("TRAVELLINE_PUBLISH_MAX_TARIFF_PAIRING_ANOMALIES", "0")),
    )
    travelline_publish_max_unmapped_categories = max(
        0,
        int(os.getenv("TRAVELLINE_PUBLISH_MAX_UNMAPPED_CATEGORIES", "0")),
    )

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
        use_travelline_rates_source=use_travelline_rates_source,
        travelline_compare_only=travelline_compare_only,
        travelline_enable_publish=travelline_enable_publish,
        travelline_fallback_to_selenium=travelline_fallback_to_selenium,
        travelline_hotel_code=travelline_hotel_code,
        travelline_base_url=travelline_base_url,
        travelline_timeout_seconds=travelline_timeout_seconds,
        travelline_publish_max_tariff_pairing_anomalies=travelline_publish_max_tariff_pairing_anomalies,
        travelline_publish_max_unmapped_categories=travelline_publish_max_unmapped_categories,
    )
