from datetime import date
from pathlib import Path

from src.domain.value_objects.category_rule import PricingMode
from src.infrastructure.loaders.category_rules_loader import load_category_rules


_TEST_TMP_DIR = Path(".tmp_tests")
_TEST_TMP_DIR.mkdir(exist_ok=True)


def _write_test_csv(content: str) -> Path:
    path = _TEST_TMP_DIR / "category_rules_test.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_category_rules_uses_first_row_for_same_group():
    csv_path = _write_test_csv(
        "\n".join(
            [
                "Категория,Группа,Вместимость_взрослые,FreeInfants,PricingMode,Оплата_4_13",
                'Deluxe A,DELUXE,2,1,PER_ADULT,"(12.07.2026-17.08.2026) - 10000 рублей, остальные даты - 5000 рублей"',
                'Deluxe B,DELUXE,99,99,FLAT,"(01.01.2026-10.01.2026) - 1 рублей, остальные даты - 1 рублей"',
            ]
        )
    )

    category_to_group, rules, policies = load_category_rules(csv_path)
    assert category_to_group["Deluxe A"] == "DELUXE"

    assert rules["DELUXE"].capacity_adults == 2
    assert rules["DELUXE"].free_infants == 1
    assert rules["DELUXE"].pricing_mode == PricingMode.PER_ADULT

    policy = policies["DELUXE"]
    assert policy.amount_for(date(2026, 7, 13)).amount == 10000
    assert policy.amount_for(date(2026, 9, 1)).amount == 5000


def test_load_category_rules_flat_or_empty_policy_is_zero():
    csv_path = _write_test_csv(
        "\n".join(
            [
                "Категория,Группа,Вместимость_взрослые,FreeInfants,PricingMode,Оплата_4_13",
                "Villa,VILLA,8,2,FLAT,",
            ]
        )
    )

    _, rules, policies = load_category_rules(csv_path)

    assert rules["VILLA"].pricing_mode == PricingMode.FLAT
    assert policies["VILLA"].amount_for(date(2026, 7, 13)).is_zero()


def test_load_category_rules_dash_free_infants_treated_as_zero():
    csv_path = _write_test_csv(
        "\n".join(
            [
                "Категория,Группа,Вместимость_взрослые,FreeInfants,PricingMode,Оплата_4_13",
                "Suite A,SUITE,4,-,PER_ADULT,",
            ]
        )
    )

    _, rules, _ = load_category_rules(csv_path)
    assert rules["SUITE"].free_infants == 0
