from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import BIGINT, TEXT, TIMESTAMP, Column, Integer, MetaData, Table, create_engine, select, text

from src.application.dto.admin_dashboard import AdminEventEntry
from src.application.ports.admin_events_repository import AdminEventsRepository


metadata = MetaData()

admin_events_table = Table(
    "admin_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_type", TEXT, nullable=False),
    Column("status", TEXT, nullable=False),
    Column("trigger", TEXT, nullable=True),
    Column("message", TEXT, nullable=True),
    Column("user_id", BIGINT, nullable=True),
    Column("created_at", TIMESTAMP, nullable=False),
)


class PostgresAdminEventsRepository(AdminEventsRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresAdminEventsRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema()

    def _init_schema(self) -> None:
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_events_type_time ON admin_events(event_type, created_at DESC)"))

    def log_event(
        self,
        *,
        event_type: str,
        status: str,
        created_at: datetime,
        trigger: str | None = None,
        message: str | None = None,
        user_id: int | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                admin_events_table.insert(),
                {
                    "event_type": event_type,
                    "status": status,
                    "trigger": trigger,
                    "message": message,
                    "user_id": user_id,
                    "created_at": created_at,
                },
            )

    def list_since(self, *, since: datetime, event_types: set[str] | None = None) -> list[AdminEventEntry]:
        stmt = select(admin_events_table).where(admin_events_table.c.created_at >= since).order_by(admin_events_table.c.created_at.desc())
        if event_types:
            stmt = stmt.where(admin_events_table.c.event_type.in_(sorted(event_types)))

        out: list[AdminEventEntry] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                out.append(
                    AdminEventEntry(
                        event_type=row["event_type"],
                        status=row["status"],
                        trigger=row["trigger"],
                        message=row["message"],
                        user_id=row["user_id"],
                        created_at=row["created_at"],
                    )
                )
        return out
