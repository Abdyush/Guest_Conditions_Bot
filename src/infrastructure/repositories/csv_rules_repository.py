from __future__ import annotations

from pathlib import Path

from src.application.ports.rules_repository import RulesRepository
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.value_objects.category_rule import CategoryRule
from src.infrastructure.loaders.category_rules_loader import load_category_rules


class CsvRulesRepository(RulesRepository):
    def __init__(self, *, rules_csv_path: str | Path):
        self._rules_csv_path = Path(rules_csv_path)
        self._cache: tuple[dict[str, str], dict[str, CategoryRule], dict[str, ChildSupplementPolicy]] | None = None

    def _load(self) -> tuple[dict[str, str], dict[str, CategoryRule], dict[str, ChildSupplementPolicy]]:
        if self._cache is None:
            self._cache = load_category_rules(self._rules_csv_path)
        return self._cache

    def get_group_rules(self) -> dict[str, CategoryRule]:
        return self._load()[1]

    def get_child_policies(self) -> dict[str, ChildSupplementPolicy]:
        return self._load()[2]

    def get_category_to_group(self) -> dict[str, str]:
        return self._load()[0]
