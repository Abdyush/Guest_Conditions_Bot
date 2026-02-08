from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import BuiltPeriod
from src.domain.services.pricing_service import PricingService, PricingContext
from src.domain.services.window_generator import WindowGenerator
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class DatePriceCandidate:
    day: date
    price_per_night: Money

    # контекст, чтобы объяснять гостю "почему такая цена"
    reason: str                  # "loyalty_only" | "offer_effective"
    offer_id: Optional[str]
    window_start: Optional[date]
    window_end: Optional[date]


class DatePriceSelector:
    """
    Для каждой даты выбирает минимальную "цену суток".

    Источники кандидатов:
    1) loyalty_only: по каждой ночи отдельно (без офферов)
    2) offer_effective: по окнам длиной offer.min_nights, эффективная цена = total_after / nights
       и эта цена присваивается каждой дате внутри окна
    """

    def __init__(self, pricing: PricingService):
        self._pricing = pricing

    def best_prices_by_date(
        self,
        *,
        daily_rates: Iterable[DailyRate],
        periods: Iterable[BuiltPeriod],
        offers: Iterable[Offer],
        ctx: PricingContext,
    ) -> dict[date, DatePriceCandidate]:
        best: dict[date, DatePriceCandidate] = {}

        # --- 1) loyalty-only по каждой ночи ---
        for r in daily_rates:
            if not r.is_available:
                continue

            price = self._pricing.price_night_loyalty_only(r.price, ctx=ctx)

            self._put_min(
                best,
                DatePriceCandidate(
                    day=r.date,
                    price_per_night=price,
                    reason="loyalty_only",
                    offer_id=None,
                    window_start=None,
                    window_end=None,
                ),
            )

        # --- 2) офферы по окнам min_nights ---
        offers_list = list(offers)
        for offer in offers_list:
            if offer.min_nights is None:
                continue

            window_size = offer.min_nights

            for period in periods:
                windows = WindowGenerator.windows(period, window_size)
                for w in windows:
                    # pricing_service сам решит: применим оффер или нет (booking/stay/category/tariff)
                    q = self._pricing.price_period(w, offer=offer, ctx=ctx)

                    # Если оффер не применился, q — это просто "как без оффера" по окну.
                    # Но нам это не нужно, потому что "loyalty_only" по каждой ночи уже добавлено.
                    # Чтобы не засорять минимум, добавляем кандидатов только если оффер реально применился.
                    if q.offer_discount == Money.zero():
                        continue

                    eff = q.effective_per_night

                    for rr in w.rates:
                        self._put_min(
                            best,
                            DatePriceCandidate(
                                day=rr.date,
                                price_per_night=eff,
                                reason="offer_effective",
                                offer_id=offer.id,
                                window_start=w.date_range.start,
                                window_end=w.date_range.end,
                            ),
                        )

        return best

    @staticmethod
    def _put_min(best: dict[date, DatePriceCandidate], cand: DatePriceCandidate) -> None:
        cur = best.get(cand.day)
        if cur is None or cand.price_per_night < cur.price_per_night:
            best[cand.day] = cand