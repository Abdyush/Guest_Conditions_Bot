from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dto.guest_notification_batch import GuestNotificationBatch
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.guests_repository import GuestsRepository
from src.application.ports.matches_run_repository import MatchesRunRepository
from src.application.ports.notifications_repository import NotificationsRepository
from src.application.ports.user_identities_repository import UserIdentitiesRepository


@dataclass(frozen=True, slots=True)
class PrepareGuestNotificationBatches:
    desired_matches_repo: MatchesRunRepository
    notifications_repo: NotificationsRepository
    guests_repo: GuestsRepository
    identities_repo: UserIdentitiesRepository
    provider: str = "telegram"
    reminder_cooldown_days: int = 7

    def execute(self, *, run_id: str, as_of_date: date) -> list[GuestNotificationBatch]:
        rows = self.desired_matches_repo.get_run_rows(run_id)
        new_rows = self.notifications_repo.filter_new(
            rows,
            as_of_date=as_of_date,
            cooldown_days=self.reminder_cooldown_days,
        )
        if not new_rows:
            return []

        guests = {guest.guest_id: guest for guest in self.guests_repo.get_active_guests() if guest.guest_id}
        rows_by_guest: dict[str, list[MatchedDateRecord]] = {}
        for row in new_rows:
            rows_by_guest.setdefault(row.guest_id, []).append(row)

        out: list[GuestNotificationBatch] = []
        for guest_id in sorted(rows_by_guest.keys()):
            telegram_user_ids: list[int] = []
            for raw_user_id in self.identities_repo.list_external_user_ids(provider=self.provider, guest_id=guest_id):
                try:
                    telegram_user_ids.append(int(raw_user_id))
                except ValueError:
                    continue
            if not telegram_user_ids:
                continue

            guest = guests.get(guest_id)
            guest_name = guest.guest_name if guest and guest.guest_name else "Гость"
            guest_rows = sorted(
                rows_by_guest[guest_id],
                key=lambda item: (
                    item.group_id,
                    item.category_name,
                    item.date,
                    item.period_end or item.date,
                    item.tariff,
                    item.new_price_minor,
                ),
            )
            category_groups = sorted(
                {
                    (row.category_name, row.group_id)
                    for row in guest_rows
                    if row.category_name and row.group_id
                },
                key=lambda item: (item[1], item[0]),
            )
            if not category_groups:
                continue

            out.append(
                GuestNotificationBatch(
                    run_id=run_id,
                    guest_id=guest_id,
                    guest_name=guest_name,
                    telegram_user_ids=telegram_user_ids,
                    rows=guest_rows,
                    category_groups=category_groups,
                )
            )
        return out
