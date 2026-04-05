from __future__ import annotations

from datetime import date

from src.infrastructure.travelline.models import TravellineRoomTypeInfo
from src.infrastructure.travelline.rates_transform import (
    BREAKFAST_TARIFF_CODE,
    FULL_PANSION_TARIFF_CODE,
    map_hotel_info_to_room_types,
    map_raw_availability_to_quotes,
    pair_tariffs_from_prices,
    transform_travelline_quotes_to_daily_rates,
)


def test_map_hotel_info_to_room_types_reads_hotels_room_types_shape() -> None:
    payload = {
        "hotels": [
            {
                "room_types": [
                    {
                        "code": "DLX",
                        "name": "Deluxe Mountain View",
                        "kind": "room",
                        "max_adult_occupancy": 3,
                        "max_occupancy": 4,
                    }
                ]
            }
        ]
    }

    out = map_hotel_info_to_room_types(payload)

    assert out["DLX"] == TravellineRoomTypeInfo(
        code="DLX",
        name="Deluxe Mountain View",
        kind="room",
        max_adult_occupancy=3,
        max_occupancy=4,
    )


def test_map_raw_availability_to_quotes_reads_realistic_room_stays_shape() -> None:
    room_types = {
        "DLX": TravellineRoomTypeInfo(
            code="DLX",
            name="Deluxe Mountain View",
            kind="room",
            max_adult_occupancy=3,
            max_occupancy=4,
        )
    }
    payload = {
        "room_stays": [
            {
                "hotel_ref": {"code": "5707"},
                "room_types": [
                    {
                        "code": "DLX",
                        "placements": [
                            {"code": "STD", "price_before_tax": 11000.0, "price_after_tax": 12000.0, "currency": "RUB"}
                        ],
                        "room_type_quota_rph": "quota-1",
                    }
                ],
                "rate_plans": [
                    {
                        "code": "rp1",
                        "cancel_penalty_group": {
                            "description": "Free cancellation until 2026-04-01",
                            "free_cancellation": True,
                            "deadline_date": "2026-04-01",
                        },
                    }
                ],
                "placement_rates": [
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [
                            {
                                "date": "2026-04-10",
                                "price_before_tax": 11000.0,
                                "price_after_tax": 12000.0,
                                "currency": "RUB",
                            }
                        ],
                    },
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [
                            {
                                "date": "2026-04-10",
                                "price_before_tax": 14000.0,
                                "price_after_tax": 15000.0,
                                "currency": "RUB",
                            }
                        ],
                    }
                ],
                "services": [{"rph": "svc-1", "applicability_type": "all_guests"}],
                "stay_dates": {"check_in": "2026-04-10", "check_out": "2026-04-11"},
                "total": {"currency": "RUB"},
            }
        ]
    }

    quotes = map_raw_availability_to_quotes(
        payload,
        hotel_code="5707",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        adults=2,
        room_types=room_types,
    )

    assert len(quotes) == 2
    assert {quote.room_type_code for quote in quotes} == {"DLX"}
    assert {quote.room_type_name for quote in quotes} == {"Deluxe Mountain View"}
    assert {quote.rate_plan_code for quote in quotes} == {"rp1"}
    assert {quote.service_rph for quote in quotes} == {"svc-1"}
    assert {quote.price_after_tax for quote in quotes} == {12000.0, 15000.0}
    assert all(quote.currency == "RUB" for quote in quotes)
    assert all(quote.free_cancellation is True for quote in quotes)
    assert all(quote.free_cancellation_deadline_date == date(2026, 4, 1) for quote in quotes)


def test_transform_quotes_builds_daily_rates_on_valid_realistic_fixture() -> None:
    room_types = {
        "DLX": TravellineRoomTypeInfo(
            code="DLX",
            name="Deluxe Mountain View",
            kind="room",
            max_adult_occupancy=3,
            max_occupancy=4,
        )
    }
    payload = {
        "room_stays": [
            {
                "hotel_ref": {"code": "5707"},
                "room_types": [{"code": "DLX", "placements": [{"code": "STD"}]}],
                "rate_plans": [{"code": "rp1"}],
                "placement_rates": [
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_before_tax": 11000.0, "price_after_tax": 12000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_before_tax": 14000.0, "price_after_tax": 15000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_before_tax": 11000.0, "price_after_tax": 12000.0, "currency": "RUB"}],
                    }
                ],
                "services": [{"rph": "svc-1"}],
            }
        ]
    }

    quotes = map_raw_availability_to_quotes(
        payload,
        hotel_code="5707",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        adults=2,
        room_types=room_types,
    )
    result = transform_travelline_quotes_to_daily_rates(
        raw_quotes=quotes,
        category_to_group={"Deluxe Mountain View": "DELUXE"},
    )

    assert len(result.quotes) == 2
    assert len(result.duplicate_keys) == 1
    assert len(result.daily_rates) == 2
    assert {item.tariff_code for item in result.daily_rates} == {
        BREAKFAST_TARIFF_CODE,
        FULL_PANSION_TARIFF_CODE,
    }
    assert {item.group_id for item in result.daily_rates} == {"DELUXE"}


def test_pair_tariffs_from_prices_supports_two_price_case() -> None:
    paired_prices, anomaly_reason = pair_tariffs_from_prices([31900.0, 37800.0])

    assert anomaly_reason is None
    assert paired_prices == {
        BREAKFAST_TARIFF_CODE: 31900.0,
        FULL_PANSION_TARIFF_CODE: 37800.0,
    }


def test_pair_tariffs_from_prices_supports_three_price_case_with_extra_guest_fee() -> None:
    paired_prices, anomaly_reason = pair_tariffs_from_prices([10000.0, 31900.0, 37800.0])

    assert anomaly_reason is None
    assert paired_prices == {
        BREAKFAST_TARIFF_CODE: 41900.0,
        FULL_PANSION_TARIFF_CODE: 47800.0,
    }


def test_pair_tariffs_from_prices_supports_three_price_case_with_eleven_thousand_extra_fee() -> None:
    paired_prices, anomaly_reason = pair_tariffs_from_prices([11000.0, 35200.0, 41600.0])

    assert anomaly_reason is None
    assert paired_prices == {
        BREAKFAST_TARIFF_CODE: 46200.0,
        FULL_PANSION_TARIFF_CODE: 52600.0,
    }


def test_pair_tariffs_from_prices_marks_four_plus_unique_prices_as_anomaly() -> None:
    paired_prices, anomaly_reason = pair_tariffs_from_prices([10000.0, 31900.0, 37800.0, 41000.0])

    assert paired_prices is None
    assert anomaly_reason == "expected_two_or_three_unique_prices"


def test_transform_quotes_builds_canonical_daily_rates_for_three_price_case() -> None:
    room_types = {
        "DLX": TravellineRoomTypeInfo(
            code="DLX",
            name="Deluxe Mountain View",
            kind="room",
            max_adult_occupancy=3,
            max_occupancy=4,
        )
    }
    payload = {
        "room_stays": [
            {
                "hotel_ref": {"code": "5707"},
                "room_types": [{"code": "DLX", "placements": [{"code": "STD"}]}],
                "rate_plans": [{"code": "rp1"}],
                "placement_rates": [
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 10000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 31900.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "DLX",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 37800.0, "currency": "RUB"}],
                    },
                ],
            }
        ]
    }

    quotes = map_raw_availability_to_quotes(
        payload,
        hotel_code="5707",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        adults=3,
        room_types=room_types,
    )
    result = transform_travelline_quotes_to_daily_rates(
        raw_quotes=quotes,
        category_to_group={"Deluxe Mountain View": "DELUXE"},
    )

    assert len(result.tariff_pairing_anomalies) == 0
    assert len(result.daily_rates) == 2
    assert {item.tariff_code for item in result.daily_rates} == {
        BREAKFAST_TARIFF_CODE,
        FULL_PANSION_TARIFF_CODE,
    }
    assert {item.price.amount_minor for item in result.daily_rates} == {4_190_000, 4_780_000}


def test_transform_quotes_marks_tariff_pairing_anomaly_without_failing() -> None:
    room_types = {
        "VLL": TravellineRoomTypeInfo(
            code="VLL",
            name="Villa Solar",
            kind="room",
            max_adult_occupancy=6,
            max_occupancy=8,
        )
    }
    payload = {
        "room_stays": [
            {
                "hotel_ref": {"code": "5707"},
                "room_types": [{"code": "VLL", "placements": [{"code": "STD"}]}],
                "rate_plans": [{"code": "rp1"}],
                "placement_rates": [
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 41000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 47000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 52000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 61000.0, "currency": "RUB"}],
                    }
                ],
            }
        ]
    }

    quotes = map_raw_availability_to_quotes(
        payload,
        hotel_code="5707",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        adults=4,
        room_types=room_types,
    )
    result = transform_travelline_quotes_to_daily_rates(
        raw_quotes=quotes,
        category_to_group={"Deluxe Mountain View": "DELUXE"},
    )

    assert len(result.tariff_pairing_anomalies) == 1
    assert len(result.daily_rates) == 0


def test_transform_quotes_records_unmapped_category_without_failing() -> None:
    room_types = {
        "VLL": TravellineRoomTypeInfo(
            code="VLL",
            name="Villa Solar",
            kind="room",
            max_adult_occupancy=6,
            max_occupancy=8,
        )
    }
    payload = {
        "room_stays": [
            {
                "hotel_ref": {"code": "5707"},
                "room_types": [{"code": "VLL", "placements": [{"code": "STD"}]}],
                "rate_plans": [{"code": "rp1"}],
                "placement_rates": [
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 41000.0, "currency": "RUB"}],
                    },
                    {
                        "room_type_code": "VLL",
                        "rate_plan_code": "rp1",
                        "placement": {"code": "STD"},
                        "rates": [{"date": "2026-04-10", "price_after_tax": 47000.0, "currency": "RUB"}],
                    }
                ],
            }
        ]
    }

    quotes = map_raw_availability_to_quotes(
        payload,
        hotel_code="5707",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        adults=4,
        room_types=room_types,
    )
    result = transform_travelline_quotes_to_daily_rates(
        raw_quotes=quotes,
        category_to_group={"Deluxe Mountain View": "DELUXE"},
    )

    assert len(result.category_mapping_mismatches) == 1
    assert {item.category_id for item in result.daily_rates} == {"Villa Solar"}
    assert {item.group_id for item in result.daily_rates} == {"Villa Solar"}
