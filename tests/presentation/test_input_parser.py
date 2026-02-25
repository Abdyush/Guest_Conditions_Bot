from __future__ import annotations

from datetime import date

import pytest

from src.presentation.telegram.mappers.input_parser import parse_period_quotes_text


def test_parse_period_quotes_text_without_groups() -> None:
    start, end, groups = parse_period_quotes_text("2026-02-25 2026-03-05")
    assert start == date(2026, 2, 25)
    assert end == date(2026, 3, 5)
    assert groups is None


def test_parse_period_quotes_text_with_groups() -> None:
    start, end, groups = parse_period_quotes_text("2026-02-25 2026-03-05 deluxe, villa")
    assert start == date(2026, 2, 25)
    assert end == date(2026, 3, 5)
    assert groups == {"DELUXE", "VILLA"}


def test_parse_period_quotes_text_raises_on_invalid() -> None:
    with pytest.raises(ValueError):
        parse_period_quotes_text("2026-03-05 2026-02-25")

