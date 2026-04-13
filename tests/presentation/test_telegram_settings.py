from __future__ import annotations

from src.presentation.telegram.settings import load_telegram_runtime_settings


def test_load_telegram_runtime_settings_defaults_to_travelline_primary_rollout(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("USE_TRAVELLINE_RATES_SOURCE", raising=False)
    monkeypatch.delenv("TRAVELLINE_COMPARE_ONLY", raising=False)
    monkeypatch.delenv("TRAVELLINE_ENABLE_PUBLISH", raising=False)
    monkeypatch.delenv("TRAVELLINE_FALLBACK_TO_SELENIUM", raising=False)
    monkeypatch.delenv("TRAVELLINE_HOTEL_CODE", raising=False)

    settings = load_telegram_runtime_settings()

    assert settings.use_travelline_rates_source is True
    assert settings.travelline_compare_only is False
    assert settings.travelline_enable_publish is True
    assert settings.travelline_fallback_to_selenium is True
    assert settings.travelline_hotel_code == ""
    assert settings.matches_lookahead_days == 180


def test_load_telegram_runtime_settings_allows_explicit_selenium_rollback_mode(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("USE_TRAVELLINE_RATES_SOURCE", "false")
    monkeypatch.setenv("TRAVELLINE_COMPARE_ONLY", "false")
    monkeypatch.setenv("TRAVELLINE_ENABLE_PUBLISH", "false")
    monkeypatch.setenv("TRAVELLINE_FALLBACK_TO_SELENIUM", "true")

    settings = load_telegram_runtime_settings()

    assert settings.use_travelline_rates_source is False
    assert settings.travelline_compare_only is False
    assert settings.travelline_enable_publish is False
    assert settings.travelline_fallback_to_selenium is True


def test_load_telegram_runtime_settings_allows_shadow_compare_mode(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("USE_TRAVELLINE_RATES_SOURCE", "false")
    monkeypatch.setenv("TRAVELLINE_ENABLE_PUBLISH", "false")
    monkeypatch.setenv("TRAVELLINE_COMPARE_ONLY", "true")
    monkeypatch.setenv("TRAVELLINE_FALLBACK_TO_SELENIUM", "true")

    settings = load_telegram_runtime_settings()

    assert settings.use_travelline_rates_source is False
    assert settings.travelline_enable_publish is False
    assert settings.travelline_compare_only is True
    assert settings.travelline_fallback_to_selenium is True
