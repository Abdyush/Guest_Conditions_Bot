from __future__ import annotations

from typing import Any, Iterable

from psycopg2.extras import Json


def ensure_system_event_log_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_event_log (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                level TEXT NOT NULL,
                source TEXT NOT NULL,
                event TEXT NOT NULL,
                message TEXT,
                meta JSONB,
                run_id TEXT,
                duration_ms INTEGER
            );
            """
        )
    conn.commit()


def insert_event(
    conn,
    *,
    level: str,
    source: str,
    event: str,
    message: str | None = None,
    meta: dict[str, Any] | None = None,
    run_id: str | None = None,
    duration_ms: int | None = None,
) -> None:
    payload = Json(meta) if meta is not None else None
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_event_log (level, source, event, message, meta, run_id, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (level, source, event, message, payload, run_id, duration_ms),
        )
    conn.commit()


def count_events(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM system_event_log")
        row = cur.fetchone()
    return int(row[0]) if row else 0


def list_events(conn, *, limit: int, offset: int = 0) -> Iterable[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, created_at, level, source, event, message, meta, run_id, duration_ms
            FROM system_event_log
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cur.fetchall()
    return [dict(row) for row in (rows or [])]
