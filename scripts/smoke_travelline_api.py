from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
import logging
import os

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test Travelline hotel_info and hotel_availability via project gateways.")
    parser.add_argument("--hotel-code", default=os.getenv("TRAVELLINE_HOTEL_CODE", "").strip())
    parser.add_argument("--date", dest="stay_date", default=date.today().isoformat())
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--base-url", default=os.getenv("TRAVELLINE_BASE_URL", "").strip())
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("TRAVELLINE_TIMEOUT_SECONDS", "20")))
    parser.add_argument(
        "--api-param",
        action="append",
        default=[],
        help="Optional static param in key=value format. Can be repeated.",
    )
    return parser


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


def _preview(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    return text[:300]


def main() -> None:
    load_env_if_available()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args()

    if not args.hotel_code:
        raise ValueError("--hotel-code or TRAVELLINE_HOTEL_CODE is required")
    if args.adults <= 0:
        raise ValueError("--adults must be > 0")

    from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
    from src.infrastructure.travelline.client import TravellineClient
    from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway

    stay_date = date.fromisoformat(args.stay_date)
    checkout = stay_date + timedelta(days=1)
    static_params = _parse_static_params(args.api_param)
    base_url = args.base_url or "https://ru-ibe.tlintegration.ru/ApiWebDistribution/BookingForm"

    client = TravellineClient(base_url=base_url, timeout_seconds=args.timeout_seconds)
    hotel_info_gateway = TravellineHotelInfoGateway(client=client, static_params=static_params)
    availability_gateway = TravellineAvailabilityGateway(client=client, static_params=static_params)

    hotel_info_response = client.get_json_response(
        "hotel_info",
        params=hotel_info_gateway.build_params(hotel_code=args.hotel_code),
    )
    print(f"hotel_info status={hotel_info_response['status']}")
    print(_preview(hotel_info_response["payload"]))

    availability_response = client.get_json_response(
        "hotel_availability",
        params=availability_gateway.build_params(
            hotel_code=args.hotel_code,
            check_in=stay_date,
            check_out=checkout,
            adults=args.adults,
        ),
    )
    print(f"hotel_availability status={availability_response['status']}")
    print(_preview(availability_response["payload"]))


if __name__ == "__main__":
    main()
