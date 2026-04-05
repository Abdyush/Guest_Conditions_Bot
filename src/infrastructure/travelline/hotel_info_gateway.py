from __future__ import annotations

from dataclasses import dataclass, field

from src.infrastructure.travelline.client import TravellineClient
from src.infrastructure.travelline.contracts import JSONDict


@dataclass(frozen=True, slots=True)
class TravellineHotelInfoGateway:
    client: TravellineClient
    hotel_code_param: str = "hotels[0].code"
    language: str = "ru-ru"
    static_params: dict[str, str] = field(default_factory=dict)

    def build_params(self, *, hotel_code: str) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            self.hotel_code_param: hotel_code,
            "language": self.language,
        }
        params.update(self.static_params)
        return params

    def fetch_raw_hotel_info(self, *, hotel_code: str) -> JSONDict:
        return self.client.get_json("hotel_info", params=self.build_params(hotel_code=hotel_code))
