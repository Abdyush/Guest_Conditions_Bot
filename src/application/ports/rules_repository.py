from __future__ import annotations

from typing import Protocol

from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.value_objects.category_rule import CategoryRule


class RulesRepository(Protocol):
    def get_group_rules(self) -> dict[str, CategoryRule]:
        ...

    def get_child_policies(self) -> dict[str, ChildSupplementPolicy]:
        ...

    def get_category_to_group(self) -> dict[str, str]:
        ...
