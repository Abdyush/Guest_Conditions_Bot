from __future__ import annotations

from src.infrastructure.repositories.postgres_user_identities_repository import normalize_phone


def test_normalize_phone_variants() -> None:
    assert normalize_phone("+7 (916) 123-45-67") == "+79161234567"
    assert normalize_phone("8 (916) 123-45-67") == "+79161234567"
    assert normalize_phone("9161234567") == "+79161234567"

