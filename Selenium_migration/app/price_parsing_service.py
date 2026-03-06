from datetime import date, timedelta
from core.ports import PriceRepository, HotelSiteGateway


class PriceParsingService:
    def __init__(self, repo: PriceRepository, gateway: HotelSiteGateway):
        print("[trace] PriceParsingService.__init__ start")
        self.repo = repo
        self.gateway = gateway

    def parse_period(self, start_date: date, days: int, progress_cb=None):
        print(f"[trace] parse_period start start_date={start_date}, days={days}")
        d = start_date
        for idx in range(days):
            print(f"[trace] parse_period processing date={d}")
            prices = self.gateway.get_regular_prices_for_date(d)
            self.repo.save_regular_prices(prices)
            if progress_cb:
                progress_cb(idx + 1, days)
            d += timedelta(days=1)
