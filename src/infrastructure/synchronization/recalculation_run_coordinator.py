from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecalculationResult:
    run_id: str
    coalesced: bool


class RecalculationRunCoordinator:
    """
    Serializes recalculation requests within a process and coalesces concurrent
    triggers into a single trailing run. Optionally protects against
    multi-process overlap with PostgreSQL advisory lock.
    """

    def __init__(self, *, database_url: str | None = None, advisory_lock_key: int = 90412031):
        self._cond = threading.Condition()
        self._running = False
        self._pending = False
        self._last_run_id = ""
        self._engine: Engine | None = None
        self._lock_key = advisory_lock_key

        url = database_url or os.getenv("DATABASE_URL")
        if url:
            try:
                self._engine = create_engine(url, future=True)
            except Exception:
                logger.exception("recalculate_lock_init_failed")

    def run(self, *, trigger: str, runner: Callable[[], str]) -> RecalculationResult:
        with self._cond:
            if self._running:
                self._pending = True
                logger.info(
                    "recalculate_request_while_running trigger=%s pending=true",
                    trigger,
                )
                while self._running:
                    self._cond.wait()
                logger.info(
                    "recalculate_request_coalesced_done trigger=%s run_id=%s",
                    trigger,
                    self._last_run_id,
                )
                return RecalculationResult(run_id=self._last_run_id, coalesced=True)

            self._running = True
            logger.info("recalculate_start trigger=%s", trigger)

        try:
            last_run_id = ""
            while True:
                run_id = self._run_once_with_lock(runner=runner, trigger=trigger)
                if run_id:
                    last_run_id = run_id

                with self._cond:
                    self._last_run_id = last_run_id
                    if self._pending:
                        self._pending = False
                        logger.info("recalculate_restart_after_pending trigger=%s", trigger)
                        continue

                    self._running = False
                    self._cond.notify_all()
                    logger.info("recalculate_finish trigger=%s run_id=%s", trigger, last_run_id)
                    return RecalculationResult(run_id=last_run_id, coalesced=False)
        except Exception:
            with self._cond:
                self._running = False
                self._cond.notify_all()
            logger.exception("recalculate_error trigger=%s", trigger)
            raise

    def _run_once_with_lock(self, *, runner: Callable[[], str], trigger: str) -> str:
        if self._engine is None:
            return runner()

        with self._engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": self._lock_key})
            logger.info(
                "recalculate_advisory_lock_acquired trigger=%s key=%s",
                trigger,
                self._lock_key,
            )
            try:
                return runner()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._lock_key})
                logger.info(
                    "recalculate_advisory_lock_released trigger=%s key=%s",
                    trigger,
                    self._lock_key,
                )
