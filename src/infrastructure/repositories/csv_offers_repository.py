from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from src.application.ports.offers_repository import OffersRepository
from src.domain.entities.offer import Offer
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff


def _csv_reader(path: Path) -> csv.DictReader:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    return csv.DictReader(StringIO(text), delimiter=";")


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"t", "true", "1", "yes"}


def _parse_date_range(raw: str) -> DateRange:
    parts = raw.strip().split("..")
    if len(parts) != 2:
        raise ValueError(f"Invalid date range: {raw}")
    start = date.fromisoformat(parts[0].strip())
    end = date.fromisoformat(parts[1].strip())
    return DateRange(start, end)


def _parse_stay_periods(raw: str) -> list[DateRange]:
    return [_parse_date_range(chunk) for chunk in raw.split("|") if chunk.strip()]


def _parse_set(raw: str | None, *, separator: str) -> set[str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    items = [x.strip() for x in text.split(separator) if x.strip()]
    return set(items) if items else None


def _parse_discount(discount_type: str, discount_value: str):
    t = discount_type.strip().upper()
    value = discount_value.strip()
    if t == "PERCENT":
        percent = Decimal(value)
        if percent <= Decimal("0") or percent >= Decimal("1"):
            raise ValueError(f"Invalid percent value: {value}")
        return PercentOff(percent)
    if t == "PAY_X_GET_Y":
        x_s, y_s = value.split("/")
        x = int(x_s.strip())
        y = int(y_s.strip())
        return PayXGetY(x, y)
    raise ValueError(f"Unsupported discount_type: {discount_type}")


class CsvOffersRepository(OffersRepository):
    def __init__(self, *, offers_csv_path: str | Path):
        self._offers_csv_path = Path(offers_csv_path)

    def get_offers(self, today: date) -> list[Offer]:
        _ = today
        offers: list[Offer] = []
        for row in _csv_reader(self._offers_csv_path):
            offer_id = (row.get("id") or "").strip()
            title = (row.get("title") or "").strip()
            description = (row.get("description") or "").strip()
            discount_type = (row.get("discount_type") or "").strip()
            discount_value = (row.get("discount_value") or "").strip()
            min_nights = int((row.get("min_nights") or "1").strip())
            stay_periods = _parse_stay_periods((row.get("stay_periods") or "").strip())
            if not stay_periods:
                continue
            booking_raw = (row.get("booking_period") or "").strip()
            booking_period = _parse_date_range(booking_raw) if booking_raw else None
            allowed_groups = _parse_set(row.get("allowed_groups"), separator=",")
            allowed_categories = _parse_set(row.get("allowed_categories"), separator="|")
            loyalty_compatible = _parse_bool(row.get("loyalty_compatible"))
            discount = _parse_discount(discount_type, discount_value)

            offers.append(
                Offer(
                    id=offer_id,
                    title=title or offer_id,
                    description=description,
                    discount=discount,
                    stay_periods=stay_periods,
                    booking_period=booking_period,
                    min_nights=min_nights,
                    allowed_groups=allowed_groups,
                    allowed_categories=allowed_categories,
                    loyalty_compatible=loyalty_compatible,
                )
            )
        return offers
