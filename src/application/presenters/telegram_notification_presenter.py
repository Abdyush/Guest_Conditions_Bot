from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from src.application.dto.best_date import BestDate


@dataclass(frozen=True, slots=True)
class TelegramNotificationPresenter:
    date_format: str = "%d.%m.%Y"

    def render_one(self, item: BestDate) -> str:
        day = item.date.strftime(self.date_format)
        period = f"{item.availability_period.start.strftime(self.date_format)}-{item.availability_period.end.strftime(self.date_format)}"
        offer_title = item.offer_title or "—"
        offer_repr = item.offer_repr or "—"
        condition = f"условие: от {item.offer_min_nights} ночей" if item.offer_id is not None and item.offer_min_nights is not None else "условие: —"
        if item.applied_bank_status is not None and item.applied_bank_percent is not None:
            bank_status = item.applied_bank_status.value
            bank_percent = self._format_percent(item.applied_bank_percent)
            loyalty_status = "—"
            loyalty_percent = "—"
        else:
            bank_status = "—"
            bank_percent = "—"
            loyalty_status = item.loyalty_status or "—"
            loyalty_percent = item.loyalty_percent or "—"

        return "; ".join(
            [
                day,
                item.category_name,
                item.group_id,
                period,
                item.tariff_code,
                str(item.old_price),
                str(item.new_price),
                offer_title,
                offer_repr,
                condition,
                f"BANK: {bank_status} {bank_percent}" if bank_status != "—" else "BANK: —",
                f"LOYALTY: {loyalty_status} {loyalty_percent}" if loyalty_status != "—" else "LOYALTY: —",
            ]
        )

    @staticmethod
    def _format_percent(percent: Decimal) -> str:
        return f"{(percent * Decimal('100')).quantize(Decimal('1'))}%"

    def render_batch(
        self,
        items: Iterable[BestDate],
        *,
        title: str = "Suitable dates",
        limit: int = 20,
    ) -> str:
        items_all = list(items)
        items_list = items_all[:limit]
        if not items_list:
            return "No suitable dates."

        lines = [f"{title}: {len(items_list)}"]
        for item in items_list:
            lines.append(self.render_one(item))

        if len(items_all) > limit:
            lines.append(f"...and {len(items_all) - limit} more")

        return "\n".join(lines)

