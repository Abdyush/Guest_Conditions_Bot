from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

from src.application.ports.rates_repository import RatesRepository
from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money


def _csv_reader(path: Path) -> csv.DictReader:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    return csv.DictReader(StringIO(text), delimiter=";")


class CsvRatesRepository(RatesRepository):
    def __init__(self, *, rates_csv_path: str | Path):
        self._rates_csv_path = Path(rates_csv_path)

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        rates: list[DailyRate] = []
        for row in _csv_reader(self._rates_csv_path):
            day = date.fromisoformat((row.get("date") or "").strip())
            if day < date_from or day > date_to:
                continue

            category_name = (row.get("category_name") or "").strip()
            group_id = (row.get("group_id") or "").strip()
            tariff_code = (row.get("tariff_code") or "").strip()
            currency = (row.get("currency") or "RUB").strip()
            amount_minor_raw = (row.get("amount_minor") or "").strip()
            adults_count_raw = (row.get("adults_count") or "").strip()
            if not category_name or not group_id or not tariff_code or not amount_minor_raw:
                continue
            adults_count = int(adults_count_raw or "1")
            amount_minor = int(amount_minor_raw)
            is_last_room = str(row.get("is_last_room") or "").strip().lower() in {"t", "true", "1", "yes"}

            rates.append(
                DailyRate(
                    date=day,
                    category_id=category_name,
                    group_id=group_id,
                    tariff_code=tariff_code,
                    adults_count=adults_count,
                    price=Money.from_minor(amount_minor, currency=currency),
                    is_available=True,
                    is_last_room=is_last_room,
                )
            )
        return rates
