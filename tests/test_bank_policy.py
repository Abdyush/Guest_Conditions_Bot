from decimal import Decimal

from src.domain.value_objects.bank import BankPolicy, BankStatus


def test_default_bank_policy_values():
    policy = BankPolicy.default()

    premier = policy.discount_for(BankStatus.SBER_PREMIER)
    assert premier.open_percent == Decimal("0.20")
    assert premier.after_offer_percent == Decimal("0.10")

    first = policy.discount_for(BankStatus.SBER_FIRST)
    assert first.open_percent == Decimal("0.25")
    assert first.after_offer_percent == Decimal("0.15")

    private = policy.discount_for(BankStatus.SBER_PRIVATE)
    assert private.open_percent == Decimal("0.30")
    assert private.after_offer_percent == Decimal("0.15")
