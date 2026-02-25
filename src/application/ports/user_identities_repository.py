from __future__ import annotations

from typing import Protocol


class UserIdentitiesRepository(Protocol):
    def upsert_identity(self, *, provider: str, external_user_id: str, guest_id: str) -> None:
        ...

    def resolve_guest_id(self, *, provider: str, external_user_id: str) -> str | None:
        ...

    def delete_identity(self, *, provider: str, external_user_id: str) -> None:
        ...
