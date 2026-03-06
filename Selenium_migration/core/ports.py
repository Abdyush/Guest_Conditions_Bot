from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from core.entities import RegularPrice, SpecialOffer, GuestDetails


class PriceRepository(ABC):
    @abstractmethod
    def save_regular_prices(self, prices: List[RegularPrice]) -> None:
        ...
        
class OffersRepository(ABC):
    @abstractmethod
    def save_offer(self, offer: SpecialOffer) -> None:
        ...
        
class HotelSiteGateway(ABC):
    @abstractmethod
    def get_regular_prices_for_date(self, dt: date) -> List[RegularPrice]:
        ...
        
class OffersSiteGateway(ABC):
    @abstractmethod
    def get_all_offers(self) -> List[SpecialOffer]: 
        ...
        
class GuestDetailsRepository(ABC):
    def get_by_telegram_id(self, telegram_id: int) -> Optional[GuestDetails]:
        ...

    def upsert(self, guest: GuestDetails) -> GuestDetails:
        ...       