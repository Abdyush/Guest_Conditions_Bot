from dataclasses import dataclass
from datetime import date
from typing import List, Optional
import uuid
from datetime import datetime
from enum import Enum


@dataclass
class RoomCategory:
    name: str
    
@dataclass
class RegularPrice:
    category: RoomCategory
    date: date
    only_breakfast: int
    full_pansion: int 
    is_last_room: bool
    
@dataclass
class StayPeriod:
    start: date
    end: date
    
@dataclass
class BookingPeriod:
    start: date
    end: date
    
@dataclass
class SpecialOffer:
    id: uuid.UUID
    title: str
    text: str
    categories: List[str]
    stay_periods: List[StayPeriod]
    booking_period: Optional[BookingPeriod]
    formula: Optional[str]
    min_days: Optional[int]
    loyalty_compatible: Optional[bool]
    
class LoyaltyStatus(str, Enum):
    DIAMOND = "diamond"
    GOLD = "gold"
    PLATINUM = "platinum"
    BRONZE = "bronze"
    SILVER = "silver"
    WHITE = "white"

LOYALTY_DISCOUNTS = {
    LoyaltyStatus.DIAMOND: 0.15,
    LoyaltyStatus.GOLD: 0.10,
    LoyaltyStatus.PLATINUM: 0.12,
    LoyaltyStatus.BRONZE: 0.07,
    LoyaltyStatus.SILVER: 0.08,
    LoyaltyStatus.WHITE: 0.05,
}

TYPES_OF_CATEGORIES = [
    'Делюкс',
    'Семейный люкс',
    'Апартаменты СПА',
    'Люкс Элегант',
    'Коннект делюкс',
    'Апартаменты в японском саду «имение Сёгуна»',
    'Королевский люкс',
    'Пентхаус',
    'Вилла',
]

@dataclass
class GuestDetails:
    id: int | None
    telegram_id: int

    first_name: str
    last_name: str

    adults: int
    teens: int  # 4–17 лет
    infant: int # 0–3 лет

    preferred_categories: List[str]

    loyalty_status: LoyaltyStatus
    desired_price_per_night: int

    created_at: datetime | None = None
    
