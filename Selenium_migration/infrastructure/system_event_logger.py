from __future__ import annotations

from typing import Any

from infrastructure.db.common_db import get_connection
from infrastructure.db.system_event_log_repo import (
    ensure_system_event_log_table,
    insert_event,
)


def log_event(
    *,
    level: str,
    source: str,
    event: str,
    message: str | None = None,
    meta: dict[str, Any] | None = None,
    run_id: str | None = None,
    duration_ms: int | None = None,
) -> None:
    try:
        with get_connection() as conn:
            ensure_system_event_log_table(conn)
            insert_event(
                conn,
                level=level,
                source=source,
                event=event,
                message=message,
                meta=meta,
                run_id=run_id,
                duration_ms=duration_ms,
            )
    except Exception as exc:
        print(f"[warn] failed to write system_event_log: {exc}")
