from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.entities.rate import DailyRate
from src.infrastructure.contracts.daily_rate_input import DailyRateInput


@dataclass(frozen=True, slots=True)
class TravellineRoomTypeInfo:
    code: str
    name: str | None
    kind: str | None
    max_adult_occupancy: int | None
    max_occupancy: int | None


@dataclass(frozen=True, slots=True)
class TravellineAvailabilityQuote:
    hotel_code: str
    check_in: date
    check_out: date
    adults: int
    room_type_code: str
    room_type_name: str | None
    rate_plan_code: str
    service_rph: str | None
    placement_code: str | None
    price_before_tax: float | None
    price_after_tax: float | None
    currency: str | None
    cancellation_description: str | None
    free_cancellation: bool | None
    free_cancellation_deadline_date: date | None


@dataclass(frozen=True, slots=True)
class TariffPairingAnomaly:
    stay_date: date
    adults: int
    room_type_code: str
    room_type_name: str | None
    observed_prices: tuple[float, ...]
    quotes_count: int
    reason: str


@dataclass(frozen=True, slots=True)
class CategoryMappingMismatch:
    room_type_code: str
    room_type_name: str | None
    fallback_category_id: str


@dataclass(frozen=True, slots=True)
class TravellineRatesTransformResult:
    quotes: tuple[TravellineAvailabilityQuote, ...]
    daily_rate_inputs: tuple[DailyRateInput, ...]
    daily_rates: tuple[DailyRate, ...]
    duplicate_keys: tuple[str, ...]
    tariff_pairing_anomalies: tuple[TariffPairingAnomaly, ...]
    category_mapping_mismatches: tuple[CategoryMappingMismatch, ...]


@dataclass(frozen=True, slots=True)
class TravellineAdultsProcessingSummary:
    adults_count: int
    expected_requests_count: int
    attempted_count: int
    success_count: int
    fail_count: int
    collected_final_rows_count: int
    status: str


@dataclass(frozen=True, slots=True)
class TravellineDateRowsStat:
    stay_date: date
    rows_count: int


@dataclass(frozen=True, slots=True)
class TravellineCollectionDiagnostics:
    expected_dates: tuple[date, ...]
    adults_summaries: tuple[TravellineAdultsProcessingSummary, ...]
    empty_dates: tuple[date, ...]
    per_date_rows: tuple[TravellineDateRowsStat, ...]
    collection_failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TravellineCollectionResult:
    transform_result: TravellineRatesTransformResult
    diagnostics: TravellineCollectionDiagnostics
