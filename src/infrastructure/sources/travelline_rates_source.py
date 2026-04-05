from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from src.application.ports.daily_rates_source import DailyRatesSourcePort
from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway
from src.infrastructure.travelline.models import TravellineRatesTransformResult
from src.infrastructure.travelline.rates_transform import (
    map_hotel_info_to_room_types,
    map_raw_availability_to_quotes,
    transform_travelline_quotes_to_daily_rates,
)


@dataclass(frozen=True, slots=True)
class TravellineRatesSource(DailyRatesSourcePort):
    hotel_code: str
    hotel_info_gateway: TravellineHotelInfoGateway
    availability_gateway: TravellineAvailabilityGateway
    category_to_group: dict[str, str]
    adults_counts: tuple[int, ...] = (1,)

    def get_daily_rates(self, date_from: date, date_to: date) -> list:
        result = self.collect_window(date_from=date_from, date_to=date_to, adults_counts=self.adults_counts)
        return list(result.daily_rates)

    def collect_window(
        self,
        *,
        date_from: date,
        date_to: date,
        adults_counts: tuple[int, ...],
    ) -> TravellineRatesTransformResult:
        room_types = map_hotel_info_to_room_types(
            self.hotel_info_gateway.fetch_raw_hotel_info(hotel_code=self.hotel_code)
        )

        raw_quotes = []
        current = date_from
        while current <= date_to:
            checkout = current + timedelta(days=1)
            for adults in adults_counts:
                raw_payload = self.availability_gateway.fetch_raw_one_night_availability(
                    hotel_code=self.hotel_code,
                    check_in=current,
                    check_out=checkout,
                    adults=adults,
                )
                raw_quotes.extend(
                    map_raw_availability_to_quotes(
                        raw_payload,
                        hotel_code=self.hotel_code,
                        check_in=current,
                        check_out=checkout,
                        adults=adults,
                        room_types=room_types,
                    )
                )
            current = current + timedelta(days=1)

        return transform_travelline_quotes_to_daily_rates(
            raw_quotes=raw_quotes,
            category_to_group=self.category_to_group,
        )
