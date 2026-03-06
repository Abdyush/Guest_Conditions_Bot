from typing import List
from core.entities import RegularPrice
from core.ports import PriceRepository

class PostgresPriceRepository(PriceRepository):
    def __init__(self, conn):
        print("[trace] PostgresPriceRepository.__init__ start")
        self.conn = conn

    def save_regular_prices(self, prices: List[RegularPrice]):
        print(f"[trace] save_regular_prices start count={len(prices)}")
        with self.conn.cursor() as cur:
            for p in prices:
                cur.execute(
                    """
                    INSERT INTO regular_prices 
                        (room_category, date, only_breakfast, full_pansion, is_last_room)
                    VALUES 
                        (%s, %s, %s, %s, %s)
                    ON CONFLICT (room_category, date)
                    DO UPDATE SET
                        only_breakfast = EXCLUDED.only_breakfast,
                        full_pansion = EXCLUDED.full_pansion,
                        is_last_room = EXCLUDED.is_last_room;
                    """,
                    (
                        p.category.name,
                        p.date,
                        p.only_breakfast,
                        p.full_pansion,
                        p.is_last_room
                    )
                )
        self.conn.commit()
