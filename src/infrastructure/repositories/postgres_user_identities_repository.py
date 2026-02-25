from __future__ import annotations

import os

from sqlalchemy import TEXT, Column, MetaData, Table, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from src.application.ports.user_identities_repository import UserIdentitiesRepository


metadata = MetaData()

user_identities_table = Table(
    "user_identities",
    metadata,
    Column("provider", TEXT, nullable=False),
    Column("external_user_id", TEXT, nullable=False),
    Column("guest_id", TEXT, nullable=False),
)


class PostgresUserIdentitiesRepository(UserIdentitiesRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresUserIdentitiesRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_user_identities_provider_external
                    ON user_identities(provider, external_user_id);
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_identities_guest_id ON user_identities(guest_id);"))

    def upsert_identity(self, *, provider: str, external_user_id: str, guest_id: str) -> None:
        normalized_provider = provider.strip().lower()
        normalized_external_user_id = self._normalize_external_user_id(
            provider=normalized_provider,
            external_user_id=external_user_id,
        )
        normalized_guest_id = guest_id.strip()
        if not normalized_provider or not normalized_external_user_id or not normalized_guest_id:
            raise ValueError("provider, external_user_id and guest_id must be non-empty")

        stmt = insert(user_identities_table).values(
            provider=normalized_provider,
            external_user_id=normalized_external_user_id,
            guest_id=normalized_guest_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "external_user_id"],
            set_={"guest_id": normalized_guest_id},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def resolve_guest_id(self, *, provider: str, external_user_id: str) -> str | None:
        normalized_provider = provider.strip().lower()
        normalized_external_user_id = self._normalize_external_user_id(
            provider=normalized_provider,
            external_user_id=external_user_id,
        )
        if not normalized_provider or not normalized_external_user_id:
            return None

        stmt = (
            select(user_identities_table.c.guest_id)
            .where(user_identities_table.c.provider == normalized_provider)
            .where(user_identities_table.c.external_user_id == normalized_external_user_id)
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).first()
            if row is None:
                return None
            return str(row.guest_id)

    def delete_identity(self, *, provider: str, external_user_id: str) -> None:
        normalized_provider = provider.strip().lower()
        normalized_external_user_id = self._normalize_external_user_id(
            provider=normalized_provider,
            external_user_id=external_user_id,
        )
        if not normalized_provider or not normalized_external_user_id:
            return

        stmt = (
            delete(user_identities_table)
            .where(user_identities_table.c.provider == normalized_provider)
            .where(user_identities_table.c.external_user_id == normalized_external_user_id)
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    @staticmethod
    def _normalize_external_user_id(*, provider: str, external_user_id: str) -> str:
        raw = external_user_id.strip()
        if provider == "phone":
            return normalize_phone(raw)
        return raw


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return "+" + digits
    if digits.startswith("9") and len(digits) == 10:
        return "+7" + digits
    if value.strip().startswith("+") and digits:
        return "+" + digits
    return "+" + digits
