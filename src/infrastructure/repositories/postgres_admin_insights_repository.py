from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BIGINT, TEXT, TIMESTAMP, Column, MetaData, Table, create_engine, select, text

from src.application.dto.admin_dashboard import DesiredPriceByGroupStat
from src.application.ports.admin_insights_repository import AdminInsightsRepository


metadata = MetaData()

guest_details_table = Table(
    "guest_details",
    metadata,
    Column("guest_id", TEXT, primary_key=True),
    Column("name", TEXT, nullable=True),
    Column("desired_price_minor", BIGINT, nullable=False),
    Column("currency", TEXT, nullable=False),
    Column("allowed_groups", TEXT, nullable=True),
    Column("adults", BIGINT, nullable=False),
    Column("teens_4_13", BIGINT, nullable=False),
    Column("infants_0_3", BIGINT, nullable=False),
    Column("loyalty_status", TEXT, nullable=True),
    Column("bank_status", TEXT, nullable=True),
    Column("created_at", TIMESTAMP, nullable=True),
)


class PostgresAdminInsightsRepository(AdminInsightsRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresAdminInsightsRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema()

    def _init_schema(self) -> None:
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            conn.execute(text("ALTER TABLE guest_details ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))

    def total_users(self) -> int:
        with self._engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) FROM guest_details")).scalar_one()
        return int(row)

    def count_new_users_since(self, *, since: datetime) -> int | None:
        with self._engine.connect() as conn:
            null_count = conn.execute(
                text("SELECT COUNT(*) FROM guest_details WHERE created_at IS NULL")
            ).scalar_one()
            if int(null_count) > 0:
                return None
            row = conn.execute(
                text("SELECT COUNT(*) FROM guest_details WHERE created_at IS NOT NULL AND created_at >= :since"),
                {"since": since},
            ).scalar_one()
        return int(row)

    def desired_price_by_group(self) -> list[DesiredPriceByGroupStat]:
        stmt = select(
            guest_details_table.c.guest_id,
            guest_details_table.c.allowed_groups,
            guest_details_table.c.desired_price_minor,
        )
        grouped: dict[str, list[int]] = {}
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                groups = _parse_groups(row["allowed_groups"])
                if not groups:
                    groups = {"ANY"}
                for group_id in groups:
                    grouped.setdefault(group_id, []).append(int(row["desired_price_minor"]))

        out: list[DesiredPriceByGroupStat] = []
        for group_id, prices in grouped.items():
            if not prices:
                continue
            avg = int((sum(Decimal(value) for value in prices) / Decimal(len(prices))).to_integral_value())
            out.append(
                DesiredPriceByGroupStat(
                    group_id=group_id,
                    users_count=len(prices),
                    avg_price_minor=avg,
                    min_price_minor=min(prices),
                    max_price_minor=max(prices),
                )
            )
        out.sort(key=lambda item: (item.group_id, item.avg_price_minor))
        return out


def _parse_groups(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip().upper() for item in raw.split(",") if item.strip()}
