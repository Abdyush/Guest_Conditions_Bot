from typing import List
from core.entities import SpecialOffer, StayPeriod
from core.ports import OffersRepository

class PostgresOfferRepository(OffersRepository):
    def __init__(self, conn):
        self.conn = conn

    def save_offer(self, offer: SpecialOffer) -> None:
        with self.conn.cursor() as cur:
            # вставляем основную запись оффера
            cur.execute(
                """
                INSERT INTO special_offers (
                    id, title, text, categories,
                    booking_start, booking_end,
                    min_days, formula, loyalty_compatible
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    str(offer.id),
                    offer.title,
                    offer.text,
                    offer.categories,  # TEXT[]
                    offer.booking_period.start if offer.booking_period else None,
                    offer.booking_period.end if offer.booking_period else None,
                    offer.min_days,
                    offer.formula,
                    offer.loyalty_compatible,
                ),
            )

            # вставляем периоды проживания
            for p in offer.stay_periods:
                cur.execute(
                    """
                    INSERT INTO special_offer_stay_periods (
                        offer_id, stay_start, stay_end
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        str(offer.id),
                        p.start,
                        p.end,
                    ),
                )

        self.conn.commit()