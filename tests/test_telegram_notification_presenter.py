from datetime import date
from decimal import Decimal

from src.application.dto.best_date import BestDate
from src.application.presenters.telegram_notification_presenter import TelegramNotificationPresenter
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def test_render_one_loyalty_only():
    presenter = TelegramNotificationPresenter()
    item = BestDate(
        date=d(2026, 2, 10),
        category_name="Deluxe",
        group_id="DELUXE",
        availability_period=DateRange(d(2026, 2, 10), d(2026, 2, 13)),
        tariff_code="breakfast",
        old_price=Money.rub("110.00"),
        new_price=Money.rub("99.00"),
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="GOLD",
        loyalty_percent="10%",
        offer_id=None,
    )

    text = presenter.render_one(item)
    assert "; BANK: -; LOYALTY: GOLD 10%" in text.replace("—", "-")


def test_render_one_offer_includes_min_nights_condition():
    presenter = TelegramNotificationPresenter()
    item = BestDate(
        date=d(2026, 2, 10),
        category_name="VILLA",
        group_id="VILLA",
        availability_period=DateRange(d(2026, 2, 10), d(2026, 2, 15)),
        tariff_code="fullpansion",
        old_price=Money.rub("100.00"),
        new_price=Money.rub("74.25"),
        offer_title="-30% from 5 nights",
        offer_repr="30%",
        offer_min_nights=5,
        loyalty_status="GOLD",
        loyalty_percent="10%",
        offer_id="o2",
    )

    text = presenter.render_one(item)
    assert "from 5 nights" in text
    assert "30%" in text
    assert "; BANK: -; LOYALTY: GOLD 10%" in text.replace("—", "-")


def test_render_one_with_bank_hides_loyalty():
    presenter = TelegramNotificationPresenter()
    item = BestDate(
        date=d(2026, 2, 10),
        category_name="Deluxe",
        group_id="DELUXE",
        availability_period=DateRange(d(2026, 2, 10), d(2026, 2, 13)),
        tariff_code="breakfast",
        old_price=Money.rub("110.00"),
        new_price=Money.rub("88.00"),
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="GOLD",
        loyalty_percent="10%",
        offer_id=None,
        applied_bank_status=BankStatus.SBER_PREMIER,
        applied_bank_percent=Decimal("0.20"),
    )

    text = presenter.render_one(item)
    assert "; BANK: SBER_PREMIER 20%; LOYALTY: -" in text.replace("—", "-")


def test_render_batch_compact():
    presenter = TelegramNotificationPresenter()
    items = [
        BestDate(d(2026, 2, 10), "DELUXE", "DELUXE", DateRange(d(2026, 2, 10), d(2026, 2, 15)), "breakfast", Money.rub("100.00"), Money.rub("74.25"), "4=3", "4=3", 4, "GOLD", "10%", "o2"),
        BestDate(d(2026, 2, 11), "ROYAL_SUITE", "ROYAL_SUITE", DateRange(d(2026, 2, 11), d(2026, 2, 12)), "fullpansion", Money.rub("110.00"), Money.rub("99.00"), None, None, None, "GOLD", "10%", None),
    ]

    text = presenter.render_batch(items, title="Found")
    assert "Found: 2" in text
    assert "10.02.2026; DELUXE; DELUXE" in text
    assert "11.02.2026; ROYAL_SUITE; ROYAL_SUITE" in text
