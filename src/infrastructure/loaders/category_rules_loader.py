from __future__ import annotations

import csv
import re
from io import StringIO
from datetime import date
from pathlib import Path

from src.domain.services.child_supplement_policy import ChildSupplementPolicy, PeriodSupplement
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.domain.value_objects.money import Money

_PERIOD_RE = re.compile(
    r"\((?P<start>\d{2}\.\d{2}\.\d{4})\s*-\s*(?P<end>\d{2}\.\d{2}\.\d{4})\)\s*-\s*(?P<amount>[\d\s]+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_DEFAULT_RE = re.compile(r"остальные\s+даты\s*-\s*(?P<amount>[\d\s]+(?:[.,]\d+)?)", re.IGNORECASE)


def _parse_int(raw: str | None, *, field_name: str, default_if_blank: int | None = None) -> int:
    if raw is None:
        if default_if_blank is not None:
            return default_if_blank
        raise ValueError(f"Missing field: {field_name}")
    value = raw.strip().replace(" ", "")
    if not value or value in {"-", "—"}:
        if default_if_blank is not None:
            return default_if_blank
        raise ValueError(f"Empty field: {field_name}")
    return int(value)


def _parse_pricing_mode(raw: str | None) -> PricingMode:
    value = (raw or "").strip().upper()
    if value in {"FLAT", "ФЛЭТ", "ФИКС"}:
        return PricingMode.FLAT
    if value in {"PER_ADULT", "PER-ADULT", "PER ADULT"}:
        return PricingMode.PER_ADULT
    if "ADULT" in value or "ВЗРОС" in value:
        return PricingMode.PER_ADULT
    return PricingMode.FLAT


def _parse_dmy(raw: str) -> date:
    day_s, month_s, year_s = raw.split(".")
    return date(int(year_s), int(month_s), int(day_s))


def _parse_money(raw: str) -> Money:
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    return Money.rub(cleaned)


def parse_child_supplement_policy(raw_value: str | None, *, pricing_mode: PricingMode) -> ChildSupplementPolicy:
    text = (raw_value or "").strip()
    if not text or pricing_mode == PricingMode.FLAT:
        return ChildSupplementPolicy([], Money.zero())

    period_rules: list[PeriodSupplement] = []
    for match in _PERIOD_RE.finditer(text):
        period_rules.append(
            PeriodSupplement(
                start=_parse_dmy(match.group("start")),
                end=_parse_dmy(match.group("end")),
                amount=_parse_money(match.group("amount")),
            )
        )

    default_match = _DEFAULT_RE.search(text)
    default_amount = Money.zero()
    if default_match is not None:
        default_amount = _parse_money(default_match.group("amount"))

    return ChildSupplementPolicy(period_rules, default_amount)


def _csv_reader(path: Path) -> csv.DictReader:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    return csv.DictReader(StringIO(text))


def load_category_rules(
    csv_path: str | Path,
) -> tuple[dict[str, str], dict[str, CategoryRule], dict[str, ChildSupplementPolicy]]:
    path = Path(csv_path)
    category_to_group: dict[str, str] = {}
    group_rules: dict[str, CategoryRule] = {}
    child_policy_by_group: dict[str, ChildSupplementPolicy] = {}

    for row in _csv_reader(path):
        category_name = (row.get("Категория") or "").strip()
        group_id = (row.get("Группа") or "").strip()
        if not category_name or not group_id:
            continue

        category_to_group[category_name] = group_id

        if group_id in group_rules:
            continue

        pricing_mode = _parse_pricing_mode(row.get("PricingMode"))
        group_rules[group_id] = CategoryRule(
            group_id=group_id,
            capacity_adults=_parse_int(row.get("Вместимость_взрослые"), field_name="Вместимость_взрослые"),
            free_infants=_parse_int(row.get("FreeInfants"), field_name="FreeInfants", default_if_blank=0),
            pricing_mode=pricing_mode,
        )
        child_policy_by_group[group_id] = parse_child_supplement_policy(
            row.get("Оплата_4_13"),
            pricing_mode=pricing_mode,
        )

    return category_to_group, group_rules, child_policy_by_group
