from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()


@dataclass(frozen=True, slots=True)
class _ExportDebugInfo:
    room_type_code: str
    rate_plan_code: str
    service_rph: str
    placement_code: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export normalized Travelline DailyRate rows into CSV for diagnostics.",
    )
    parser.add_argument("--hotel-code", default=os.getenv("TRAVELLINE_HOTEL_CODE", "").strip())
    parser.add_argument("--start-date", default=date.today().isoformat())
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--adults", default="1,2,3,4,5,6")
    return parser


def _parse_adults(raw: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in raw.split(","):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        value = int(cleaned)
        if value <= 0:
            raise ValueError("--adults must contain only positive integers")
        out.append(value)
    if not out:
        raise ValueError("--adults must contain at least one value")
    return tuple(sorted(set(out)))


def _fallback_category_name(*, room_type_code: str, room_type_name: str | None) -> str:
    if room_type_name and room_type_name.strip():
        return room_type_name.strip()
    return room_type_code


def _build_debug_index(quotes) -> dict[tuple[str, int, str, str], _ExportDebugInfo]:
    from src.infrastructure.travelline.rates_transform import (
        BREAKFAST_TARIFF_CODE,
        FULL_PANSION_TARIFF_CODE,
        pair_tariffs_from_prices,
    )

    grouped = defaultdict(list)
    for quote in quotes:
        grouped[(quote.check_in, quote.adults, quote.room_type_code)].append(quote)

    out: dict[tuple[str, int, str, str], _ExportDebugInfo] = {}
    for (stay_date, adults_count, room_type_code), bucket in grouped.items():
        unique_prices = sorted(
            {
                float(quote.price_after_tax)
                for quote in bucket
                if quote.price_after_tax is not None
            }
        )
        paired_prices, anomaly_reason = pair_tariffs_from_prices(unique_prices)
        if paired_prices is None or anomaly_reason is not None:
            continue

        category_name = _fallback_category_name(
            room_type_code=room_type_code,
            room_type_name=bucket[0].room_type_name if bucket else None,
        )
        rate_plan_code = "|".join(sorted({quote.rate_plan_code for quote in bucket if quote.rate_plan_code}))
        service_rph = "|".join(sorted({quote.service_rph for quote in bucket if quote.service_rph}))
        placement_code = "|".join(sorted({quote.placement_code for quote in bucket if quote.placement_code}))
        debug_info = _ExportDebugInfo(
            room_type_code=room_type_code,
            rate_plan_code=rate_plan_code,
            service_rph=service_rph,
            placement_code=placement_code,
        )
        out[(stay_date.isoformat(), adults_count, category_name, BREAKFAST_TARIFF_CODE)] = debug_info
        out[(stay_date.isoformat(), adults_count, category_name, FULL_PANSION_TARIFF_CODE)] = debug_info
    return out


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

    if not args.hotel_code:
        raise ValueError("--hotel-code or TRAVELLINE_HOTEL_CODE is required")
    if args.days <= 0:
        raise ValueError("--days must be > 0")

    from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
    from src.infrastructure.sources.travelline_rates_source import TravellineRatesSource
    from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
    from src.infrastructure.travelline.client import TravellineClient
    from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway

    adults_counts = _parse_adults(args.adults)
    start_date = date.fromisoformat(args.start_date)
    end_date = start_date + timedelta(days=args.days - 1)

    client = TravellineClient(
        base_url=os.getenv("TRAVELLINE_BASE_URL", "https://ru-ibe.tlintegration.ru/ApiWebDistribution/BookingForm"),
        timeout_seconds=float(os.getenv("TRAVELLINE_TIMEOUT_SECONDS", "20")),
    )
    source = TravellineRatesSource(
        hotel_code=args.hotel_code,
        hotel_info_gateway=TravellineHotelInfoGateway(client=client),
        availability_gateway=TravellineAvailabilityGateway(client=client),
        category_to_group=PostgresRulesRepository().get_category_to_group(),
        adults_counts=adults_counts,
    )
    transform_result = source.collect_window(
        date_from=start_date,
        date_to=end_date,
        adults_counts=adults_counts,
    )

    daily_rates = sorted(
        transform_result.daily_rates,
        key=lambda rate: (
            rate.date.isoformat(),
            rate.adults_count,
            rate.category_id,
            rate.tariff_code,
        ),
    )
    debug_index = _build_debug_index(transform_result.quotes)

    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "travelline_rates_export.csv"

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "date",
                "adults_count",
                "category_id",
                "category_name",
                "group_id",
                "tariff_code",
                "price_rub",
                "raw_price_minor",
                "source",
                "room_type_code",
                "rate_plan_code",
                "service_rph",
                "placement_code",
            ],
        )
        writer.writeheader()
        for rate in daily_rates:
            debug = debug_index.get(
                (
                    rate.date.isoformat(),
                    rate.adults_count,
                    rate.category_id,
                    rate.tariff_code,
                )
            )
            writer.writerow(
                {
                    "date": rate.date.isoformat(),
                    "adults_count": rate.adults_count,
                    "category_id": rate.category_id,
                    "category_name": rate.category_id,
                    "group_id": rate.group_id or "",
                    "tariff_code": rate.tariff_code,
                    "price_rub": f"{rate.price.amount:.2f}",
                    "raw_price_minor": rate.price.amount_minor,
                    "source": "travelline",
                    "room_type_code": "" if debug is None else debug.room_type_code,
                    "rate_plan_code": "" if debug is None else debug.rate_plan_code,
                    "service_rph": "" if debug is None else debug.service_rph,
                    "placement_code": "" if debug is None else debug.placement_code,
                }
            )

    unique_categories = len({rate.category_id for rate in daily_rates})
    min_date = daily_rates[0].date.isoformat() if daily_rates else start_date.isoformat()
    max_date = daily_rates[-1].date.isoformat() if daily_rates else end_date.isoformat()

    print(f"travelline_rates_export_path={output_path}")
    print(f"total_rows={len(daily_rates)}")
    print(f"unique_categories={unique_categories}")
    print(f"date_range={min_date}..{max_date}")


if __name__ == "__main__":
    main()
