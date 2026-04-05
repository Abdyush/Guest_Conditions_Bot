from __future__ import annotations

import argparse
from datetime import date, timedelta
import os

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare active Selenium daily_rates snapshot against Travelline-derived compare-only rates.",
    )
    parser.add_argument("--hotel-code", default=os.getenv("TRAVELLINE_HOTEL_CODE", "").strip())
    parser.add_argument("--start-date", default=date.today().isoformat())
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--adults", default="1,2,3,4,5,6")
    parser.add_argument("--base-url", default=os.getenv("TRAVELLINE_BASE_URL", "").strip())
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("TRAVELLINE_TIMEOUT_SECONDS", "20")))
    parser.add_argument("--hotel-code-param", default=os.getenv("TRAVELLINE_HOTEL_CODE_PARAM", "hotels[0].code"))
    parser.add_argument("--adults-param", default=os.getenv("TRAVELLINE_ADULTS_PARAM", "criterions[0].adults"))
    parser.add_argument(
        "--api-param",
        action="append",
        default=[],
        help="Optional static param in key=value format. Can be repeated.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(ROOT / "artifacts" / "compare"),
        help="Directory for compare artifacts.",
    )
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


def _parse_static_params(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --api-param value: {value!r}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --api-param key in: {value!r}")
        out[key] = raw.strip()
    return out


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

    if not args.hotel_code:
        raise ValueError("--hotel-code or TRAVELLINE_HOTEL_CODE is required")
    if args.days <= 0:
        raise ValueError("--days must be > 0")

    from pathlib import Path

    from src.infrastructure.parsers.travelline_rates_parser_runner import TravellineRatesParserRunner
    from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
    from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
    from src.infrastructure.sources.travelline_rates_source import TravellineRatesSource
    from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
    from src.infrastructure.travelline.client import TravellineClient
    from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway

    adults_counts = _parse_adults(args.adults)
    static_params = _parse_static_params(args.api_param)
    start_date = date.fromisoformat(args.start_date)
    end_date = start_date + timedelta(days=args.days - 1)
    base_url = args.base_url or "https://ru-ibe.tlintegration.ru/ApiWebDistribution/BookingForm"

    client = TravellineClient(base_url=base_url, timeout_seconds=args.timeout_seconds)
    source = TravellineRatesSource(
        hotel_code=args.hotel_code,
        hotel_info_gateway=TravellineHotelInfoGateway(
            client=client,
            hotel_code_param=args.hotel_code_param,
            static_params=static_params,
        ),
        availability_gateway=TravellineAvailabilityGateway(
            client=client,
            hotel_code_param=os.getenv("TRAVELLINE_AVAILABILITY_HOTEL_CODE_PARAM", "criterions[0].hotels[0].code"),
            adults_param=args.adults_param,
            static_params=static_params,
        ),
        category_to_group=PostgresRulesRepository().get_category_to_group(),
        adults_counts=adults_counts,
    )
    runner = TravellineRatesParserRunner(
        source=source,
        rates_repo=PostgresDailyRatesRepository(),
        artifacts_dir=Path(args.artifacts_dir),
    )
    result = runner.run_compare_only(
        date_from=start_date,
        date_to=end_date,
        adults_counts=adults_counts,
    )

    print("travelline compare complete")
    print(f"selenium_total_rows={result.summary.selenium_total_rows}")
    print(f"travelline_total_rows={result.summary.travelline_total_rows}")
    print(f"selenium_only_rows={result.summary.selenium_only_rows}")
    print(f"travelline_only_rows={result.summary.travelline_only_rows}")
    print(f"exact_price_matches={result.summary.exact_price_matches}")
    print(f"price_mismatches={result.summary.price_mismatches}")
    print(f"unmapped_categories={result.summary.unmapped_categories}")
    print(f"tariff_pairing_anomalies={result.summary.tariff_pairing_anomalies}")
    print(f"summary_path={result.summary.summary_path}")
    print(f"diff_path={result.summary.diff_path}")


if __name__ == "__main__":
    main()
