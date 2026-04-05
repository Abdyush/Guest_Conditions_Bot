from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from src.infrastructure.contracts.daily_rate_input import DailyRateInput
from src.infrastructure.mappers.to_domain import map_daily_rates
from src.infrastructure.travelline.contracts import JSONDict, JSONValue
from src.infrastructure.travelline.models import (
    CategoryMappingMismatch,
    TariffPairingAnomaly,
    TravellineAvailabilityQuote,
    TravellineRatesTransformResult,
    TravellineRoomTypeInfo,
)


logger = logging.getLogger(__name__)

BREAKFAST_TARIFF_CODE = "breakfast"
FULL_PANSION_TARIFF_CODE = "fullpansion"
UNKNOWN_TARIFF_CODE = "travelline_anomaly"


def map_hotel_info_to_room_types(raw_payload: JSONDict) -> dict[str, TravellineRoomTypeInfo]:
    raw_room_types = _extract_room_types(raw_payload)
    out: dict[str, TravellineRoomTypeInfo] = {}
    for item in raw_room_types:
        code = _first_str(item, "room_type_code", "roomTypeCode", "code")
        if not code:
            continue
        out[code] = TravellineRoomTypeInfo(
            code=code,
            name=_first_str(item, "room_type_name", "roomTypeName", "name"),
            kind=_first_str(item, "kind", "room_kind", "roomKind"),
            max_adult_occupancy=_first_int(item, "max_adult_occupancy", "maxAdultOccupancy", "max_adults"),
            max_occupancy=_first_int(item, "max_occupancy", "maxOccupancy", "max_guests"),
        )
    return out


def map_raw_availability_to_quotes(
    raw_payload: JSONDict,
    *,
    hotel_code: str,
    check_in: date,
    check_out: date,
    adults: int,
    room_types: dict[str, TravellineRoomTypeInfo],
) -> list[TravellineAvailabilityQuote]:
    room_stays = _extract_room_stays(raw_payload)
    quotes: list[TravellineAvailabilityQuote] = []
    skipped_reasons: dict[str, int] = defaultdict(int)

    for room_stay in room_stays:
        room_types_in_stay = _extract_room_type_nodes(room_stay)
        if not room_types_in_stay:
            skipped_reasons["missing_room_types"] += 1
            continue
        room_type_code = _first_str(room_types_in_stay[0], "room_type_code", "roomTypeCode", "code")
        if not room_type_code:
            skipped_reasons["missing_room_type_code"] += 1
            continue
        room_type = room_types.get(room_type_code)
        room_type_name = (
            room_type.name
            if room_type is not None
            else _first_str(room_types_in_stay[0], "room_type_name", "roomTypeName", "name")
        )
        rate_plan_nodes = _extract_rate_plan_nodes(room_stay)
        rate_plan = rate_plan_nodes[0] if rate_plan_nodes else room_stay
        rate_plan_code = _first_str(rate_plan, "rate_plan_code", "ratePlanCode", "code") or "unknown_rate_plan"
        service_rph = _extract_service_rph(room_stay)
        placement_rates = _extract_placement_rate_nodes(room_stay)
        if not placement_rates:
            skipped_reasons["missing_placement_rates"] += 1
            continue

        extracted_in_stay = 0

        for placement_rate in placement_rates:
            placement_room_type_code = _first_str(placement_rate, "room_type_code", "roomTypeCode")
            if placement_room_type_code and placement_room_type_code != room_type_code:
                continue
            placement_rate_plan_code = _first_str(placement_rate, "rate_plan_code", "ratePlanCode") or rate_plan_code
            nightly_rates = _extract_nightly_rates(placement_rate)
            if not nightly_rates:
                price_before_tax = _extract_price(placement_rate, "price_before_tax", "priceBeforeTax", "before_tax")
                price_after_tax = _extract_price(
                    placement_rate,
                    "price_after_tax",
                    "priceAfterTax",
                    "amount",
                    "total_price",
                    "totalPrice",
                )
                if price_after_tax is None:
                    skipped_reasons["missing_price"] += 1
                    continue
                quotes.append(
                    TravellineAvailabilityQuote(
                        hotel_code=hotel_code,
                        check_in=check_in,
                        check_out=check_out,
                        adults=adults,
                        room_type_code=room_type_code,
                        room_type_name=room_type_name,
                        rate_plan_code=placement_rate_plan_code,
                        service_rph=service_rph,
                        placement_code=_extract_placement_code(placement_rate),
                        price_before_tax=price_before_tax,
                        price_after_tax=price_after_tax,
                        currency=_extract_currency(placement_rate, room_stay),
                        cancellation_description=_extract_cancellation_description(placement_rate, rate_plan, room_stay),
                        free_cancellation=_extract_free_cancellation_flag(placement_rate, rate_plan, room_stay),
                        free_cancellation_deadline_date=_extract_deadline_date(placement_rate, rate_plan, room_stay),
                    )
                )
                extracted_in_stay += 1
                continue

            for nightly_rate in nightly_rates:
                rate_date = _first_date(nightly_rate, "date", "stay_date", "stayDate")
                if rate_date is not None and rate_date != check_in:
                    continue
                price_before_tax = _extract_price(
                    nightly_rate,
                    "price_before_tax",
                    "priceBeforeTax",
                    "before_tax",
                )
                if price_before_tax is None:
                    price_before_tax = _extract_price(placement_rate, "price_before_tax", "priceBeforeTax", "before_tax")
                price_after_tax = _extract_price(
                    nightly_rate,
                    "price_after_tax",
                    "priceAfterTax",
                    "amount",
                    "total_price",
                    "totalPrice",
                )
                if price_after_tax is None:
                    price_after_tax = _extract_price(
                        placement_rate,
                        "price_after_tax",
                        "priceAfterTax",
                        "amount",
                        "total_price",
                        "totalPrice",
                    )
                if price_after_tax is None:
                    skipped_reasons["missing_price"] += 1
                    continue
                quotes.append(
                    TravellineAvailabilityQuote(
                        hotel_code=hotel_code,
                        check_in=check_in,
                        check_out=check_out,
                        adults=adults,
                        room_type_code=room_type_code,
                        room_type_name=room_type_name,
                        rate_plan_code=placement_rate_plan_code,
                        service_rph=service_rph,
                        placement_code=_extract_placement_code(placement_rate),
                        price_before_tax=price_before_tax,
                        price_after_tax=price_after_tax,
                        currency=_extract_currency(nightly_rate, placement_rate, room_stay),
                        cancellation_description=_extract_cancellation_description(
                            nightly_rate,
                            placement_rate,
                            rate_plan,
                            room_stay,
                        ),
                        free_cancellation=_extract_free_cancellation_flag(
                            nightly_rate,
                            placement_rate,
                            rate_plan,
                            room_stay,
                        ),
                        free_cancellation_deadline_date=_extract_deadline_date(
                            nightly_rate,
                            placement_rate,
                            rate_plan,
                            room_stay,
                        ),
                    )
                )
                extracted_in_stay += 1

        if extracted_in_stay == 0:
            skipped_reasons["no_quotes_extracted"] += 1

    logger.info(
        "travelline_availability_extract room_stays=%s quotes=%s skipped=%s",
        len(room_stays),
        len(quotes),
        dict(sorted(skipped_reasons.items())),
    )

    return quotes


def deduplicate_quotes(quotes: Iterable[TravellineAvailabilityQuote]) -> tuple[list[TravellineAvailabilityQuote], list[str]]:
    out: list[TravellineAvailabilityQuote] = []
    duplicate_keys: list[str] = []
    seen: set[str] = set()
    for quote in quotes:
        key = _quote_dedup_key(quote)
        if key in seen:
            duplicate_keys.append(key)
            continue
        seen.add(key)
        out.append(quote)
    return out, duplicate_keys


def pair_tariffs_from_prices(observed_prices: Iterable[float]) -> tuple[dict[str, float] | None, str | None]:
    unique_prices = sorted({_normalize_price_value(price) for price in observed_prices})
    if len(unique_prices) == 2:
        low_price, high_price = unique_prices
        return {
            BREAKFAST_TARIFF_CODE: low_price,
            FULL_PANSION_TARIFF_CODE: high_price,
        }, None
    if len(unique_prices) == 3:
        extra_price, base_low_price, base_high_price = unique_prices
        return {
            BREAKFAST_TARIFF_CODE: _normalize_price_value(base_low_price + extra_price),
            FULL_PANSION_TARIFF_CODE: _normalize_price_value(base_high_price + extra_price),
        }, None
    return None, "expected_two_or_three_unique_prices"


def build_canonical_daily_rate_inputs(
    quotes: Iterable[TravellineAvailabilityQuote],
    *,
    category_to_group: dict[str, str],
) -> tuple[list[DailyRateInput], list[TariffPairingAnomaly], list[CategoryMappingMismatch]]:
    grouped: dict[tuple[date, int, str], list[TravellineAvailabilityQuote]] = defaultdict(list)
    for quote in quotes:
        grouped[(quote.check_in, quote.adults, quote.room_type_code)].append(quote)

    inputs: list[DailyRateInput] = []
    anomalies: list[TariffPairingAnomaly] = []
    normalized_mapping = _build_category_group_mapping(category_to_group)
    mismatches: list[CategoryMappingMismatch] = []
    mismatch_keys: set[tuple[str, str]] = set()

    for (stay_date, adults, room_type_code), bucket in grouped.items():
        unique_prices = sorted(
            {
                _normalize_price_value(quote.price_after_tax)
                for quote in bucket
                if quote.price_after_tax is not None
            }
        )
        paired_prices, anomaly_reason = pair_tariffs_from_prices(unique_prices)
        if paired_prices is None or anomaly_reason is not None:
            anomalies.append(
                TariffPairingAnomaly(
                    stay_date=stay_date,
                    adults=adults,
                    room_type_code=room_type_code,
                    room_type_name=bucket[0].room_type_name if bucket else None,
                    observed_prices=tuple(unique_prices),
                    quotes_count=len(bucket),
                    reason=anomaly_reason or "unsupported_unique_prices",
                )
            )
            logger.warning(
                "travelline_tariff_pairing_anomaly date=%s adults=%s room_type_code=%s unique_prices=%s quotes=%s",
                stay_date.isoformat(),
                adults,
                room_type_code,
                list(unique_prices),
                len(bucket),
            )
            continue

        representative_quote = _select_representative_quote(bucket)
        category_name = _fallback_category_name(representative_quote)
        group_id = normalized_mapping.get(_normalize_category(category_name))
        if group_id is None:
            key = (representative_quote.room_type_code, category_name)
            if key not in mismatch_keys:
                mismatch_keys.add(key)
                mismatches.append(
                    CategoryMappingMismatch(
                        room_type_code=representative_quote.room_type_code,
                        room_type_name=representative_quote.room_type_name,
                        fallback_category_id=category_name,
                    )
                )
                logger.warning(
                    "travelline_category_mapping_mismatch room_type_code=%s room_type_name=%s fallback=%s",
                    representative_quote.room_type_code,
                    representative_quote.room_type_name,
                    category_name,
                )
            group_id = category_name

        for tariff_code in (BREAKFAST_TARIFF_CODE, FULL_PANSION_TARIFF_CODE):
            amount_minor = _price_to_minor(paired_prices[tariff_code])
            if amount_minor is None:
                continue
            inputs.append(
                DailyRateInput(
                    date=representative_quote.check_in,
                    category_name=category_name,
                    group_id=group_id,
                    tariff_code=tariff_code,
                    adults_count=representative_quote.adults,
                    amount_minor=amount_minor,
                    currency=(representative_quote.currency or "RUB").upper(),
                    # Travelline compare mode does not have a reliable last-room signal yet.
                    is_last_room=False,
                    source="travelline_compare",
                )
            )
    return inputs, anomalies, mismatches


def transform_travelline_quotes_to_daily_rates(
    *,
    raw_quotes: Iterable[TravellineAvailabilityQuote],
    category_to_group: dict[str, str],
) -> TravellineRatesTransformResult:
    raw_quotes_list = list(raw_quotes)
    deduped_quotes, duplicate_keys = deduplicate_quotes(raw_quotes_list)
    daily_rate_inputs, anomalies, mismatches = build_canonical_daily_rate_inputs(
        deduped_quotes,
        category_to_group=category_to_group,
    )
    daily_rates = map_daily_rates(daily_rate_inputs)
    logger.info(
        "travelline_transform_summary raw_quotes=%s deduped_quotes=%s daily_rate_inputs=%s daily_rates=%s anomalies=%s mismatches=%s duplicates=%s",
        len(raw_quotes_list),
        len(deduped_quotes),
        len(daily_rate_inputs),
        len(daily_rates),
        len(anomalies),
        len(mismatches),
        len(duplicate_keys),
    )
    return TravellineRatesTransformResult(
        quotes=tuple(deduped_quotes),
        daily_rate_inputs=tuple(daily_rate_inputs),
        daily_rates=tuple(daily_rates),
        duplicate_keys=tuple(duplicate_keys),
        tariff_pairing_anomalies=tuple(anomalies),
        category_mapping_mismatches=tuple(mismatches),
    )


def _extract_room_types(payload: JSONDict) -> list[JSONDict]:
    hotels = payload.get("hotels")
    if isinstance(hotels, list):
        out: list[JSONDict] = []
        for hotel in hotels:
            if isinstance(hotel, dict):
                hotel_room_types = hotel.get("room_types") or hotel.get("roomTypes")
                if isinstance(hotel_room_types, list):
                    out.extend(item for item in hotel_room_types if isinstance(item, dict))
        if out:
            return out
    for key in ("room_types", "roomTypes"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    hotel_info = payload.get("hotel_info") or payload.get("hotelInfo")
    if isinstance(hotel_info, dict):
        return _extract_room_types(hotel_info)
    return []


def _extract_room_stays(payload: JSONDict) -> list[JSONDict]:
    for key in ("room_stays", "roomStays"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for key in ("data", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _extract_room_stays(value)
            if nested:
                return nested
    return []


def _extract_placement_rates(room_stay: JSONDict) -> list[JSONDict]:
    value = room_stay.get("placement_rates") or room_stay.get("placementRates")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_room_type_nodes(room_stay: JSONDict) -> list[JSONDict]:
    value = room_stay.get("room_types") or room_stay.get("roomTypes")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_rate_plan_nodes(room_stay: JSONDict) -> list[JSONDict]:
    value = room_stay.get("rate_plans") or room_stay.get("ratePlans")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_placement_rate_nodes(room_stay: JSONDict) -> list[JSONDict]:
    return _extract_placement_rates(room_stay)


def _extract_nightly_rates(placement_rate: JSONDict) -> list[JSONDict]:
    value = placement_rate.get("rates")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_placement_code(placement_rate: JSONDict) -> str | None:
    direct = _first_str(placement_rate, "placement_code", "placementCode", "code")
    if direct:
        return direct
    placement = placement_rate.get("placement")
    if isinstance(placement, dict):
        return _first_str(placement, "placement_code", "placementCode", "code")
    return None


def _extract_service_rph(room_stay: JSONDict) -> str | None:
    services = room_stay.get("services")
    if isinstance(services, list):
        for item in services:
            if isinstance(item, dict):
                rph = _first_str(item, "rph", "service_rph", "serviceRph")
                if rph:
                    return rph
    if isinstance(services, dict):
        return _first_str(services, "rph", "service_rph", "serviceRph")
    return None


def _extract_currency(*items: JSONDict) -> str | None:
    for item in items:
        currency = _first_str(item, "currency", "currency_code", "currencyCode")
        if currency:
            return currency
        total = item.get("total")
        if isinstance(total, dict):
            currency = _first_str(total, "currency", "currency_code", "currencyCode")
            if currency:
                return currency
    return None


def _extract_cancellation_description(*items: JSONDict) -> str | None:
    for item in items:
        cancellation = item.get("cancellation")
        if isinstance(cancellation, dict):
            text = _first_str(cancellation, "description", "text", "policy")
            if text:
                return text
        text = _first_str(item, "cancellation_description", "cancellationDescription")
        if text:
            return text
        cancel_group = item.get("cancel_penalty_group") or item.get("cancelPenaltyGroup")
        if isinstance(cancel_group, dict):
            text = _first_str(cancel_group, "description", "text", "title", "name", "policy")
            if text:
                return text
    return None


def _extract_free_cancellation_flag(*items: JSONDict) -> bool | None:
    for item in items:
        cancellation = item.get("cancellation")
        if isinstance(cancellation, dict):
            value = _first_bool(cancellation, "free_cancellation", "freeCancellation", "is_free")
            if value is not None:
                return value
        value = _first_bool(item, "free_cancellation", "freeCancellation")
        if value is not None:
            return value
        cancel_group = item.get("cancel_penalty_group") or item.get("cancelPenaltyGroup")
        if isinstance(cancel_group, dict):
            value = _first_bool(cancel_group, "free_cancellation", "freeCancellation", "is_free", "isFree")
            if value is not None:
                return value
    return None


def _extract_deadline_date(*items: JSONDict) -> date | None:
    for item in items:
        cancellation = item.get("cancellation")
        if isinstance(cancellation, dict):
            parsed = _first_date(
                cancellation,
                "free_cancellation_deadline_date",
                "freeCancellationDeadlineDate",
                "deadline_date",
                "deadlineDate",
            )
            if parsed is not None:
                return parsed
        parsed = _first_date(item, "free_cancellation_deadline_date", "freeCancellationDeadlineDate")
        if parsed is not None:
            return parsed
        cancel_group = item.get("cancel_penalty_group") or item.get("cancelPenaltyGroup")
        if isinstance(cancel_group, dict):
            parsed = _first_date(
                cancel_group,
                "free_cancellation_deadline_date",
                "freeCancellationDeadlineDate",
                "deadline_date",
                "deadlineDate",
                "date",
            )
            if parsed is not None:
                return parsed
    return None


def _extract_price(item: JSONDict, *keys: str) -> float | None:
    for key in keys:
        parsed = _coerce_float(item.get(key))
        if parsed is not None:
            return parsed
    total = item.get("total")
    if isinstance(total, dict):
        for key in keys:
            parsed = _coerce_float(total.get(key))
            if parsed is not None:
                return parsed
    return None


def _first_str(item: JSONDict, *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(item: JSONDict, *keys: str) -> int | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _first_bool(item: JSONDict, *keys: str) -> bool | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
    return None


def _first_date(item: JSONDict, *keys: str) -> date | None:
    for key in keys:
        parsed = _coerce_date(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _coerce_float(value: JSONValue | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(" ", "").replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _coerce_date(value: JSONValue | None) -> date | None:
    if not isinstance(value, str):
        return None
    head = value.strip().split("T", 1)[0]
    if not head:
        return None
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


def _quote_dedup_key(quote: TravellineAvailabilityQuote) -> str:
    return "|".join(
        [
            quote.hotel_code,
            quote.check_in.isoformat(),
            quote.check_out.isoformat(),
            str(quote.adults),
            quote.room_type_code,
            quote.rate_plan_code,
            quote.service_rph or "",
            quote.placement_code or "",
            str(_normalize_price_value(quote.price_after_tax)),
        ]
    )


def _quote_runtime_key(quote: TravellineAvailabilityQuote) -> str:
    return "|".join(
        [
            quote.check_in.isoformat(),
            str(quote.adults),
            quote.room_type_code,
            quote.rate_plan_code,
            quote.service_rph or "",
            quote.placement_code or "",
            str(_normalize_price_value(quote.price_after_tax)),
        ]
    )


def _normalize_price_value(value: float | None) -> float:
    if value is None:
        return -1.0
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_category_group_mapping(category_to_group: dict[str, str]) -> dict[str, str]:
    return {_normalize_category(category): group for category, group in category_to_group.items()}


def _normalize_category(value: str) -> str:
    return " ".join(value.split()).casefold()


def _select_representative_quote(bucket: list[TravellineAvailabilityQuote]) -> TravellineAvailabilityQuote:
    for quote in bucket:
        if quote.room_type_name and quote.currency:
            return quote
    return bucket[0]


def _fallback_category_name(quote: TravellineAvailabilityQuote) -> str:
    if quote.room_type_name and quote.room_type_name.strip():
        return quote.room_type_name.strip()
    return quote.room_type_code


def _price_to_minor(value: float | None) -> int | None:
    if value is None:
        return None
    minor = (Decimal(str(value)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)
