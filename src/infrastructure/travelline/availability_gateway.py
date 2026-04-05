from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.infrastructure.travelline.client import TravellineClient
from src.infrastructure.travelline.contracts import JSONDict


@dataclass(frozen=True, slots=True)
class TravellineAvailabilityGateway:
    client: TravellineClient
    hotel_code_param: str = "criterions[0].hotels[0].code"
    dates_param: str = "criterions[0].dates"
    adults_param: str = "criterions[0].adults"
    language: str = "ru-ru"
    static_params: dict[str, str] = field(default_factory=dict)

    def build_params(
        self,
        *,
        hotel_code: str,
        check_in: date,
        check_out: date,
        adults: int,
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "include_all_placements": "false",
            "include_promo_restricted": "true",
            "include_rates": "true",
            "include_transfers": "true",
            "language": self.language,
            self.adults_param: adults,
            self.dates_param: f"{check_in.isoformat()};{check_out.isoformat()}",
            self.hotel_code_param: hotel_code,
        }
        params.update(self.static_params)
        return params

    def fetch_raw_one_night_availability(
        self,
        *,
        hotel_code: str,
        check_in: date,
        check_out: date,
        adults: int,
    ) -> JSONDict:
        return self.client.get_json(
            "hotel_availability",
            params=self.build_params(
                hotel_code=hotel_code,
                check_in=check_in,
                check_out=check_out,
                adults=adults,
            ),
        )
