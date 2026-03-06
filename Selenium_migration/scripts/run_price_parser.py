import csv
import multiprocessing
import os
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from multiprocessing import Manager, Process
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from selenium import webdriver

from app.price_parsing_service import PriceParsingService
from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_price_repo import PostgresPriceRepository
from infrastructure.system_event_logger import log_event
from infrastructure.selen.hotel_gateway import SeleniumHotelGateway
from parser.funcs.common_funcs import create_browser_options

WORKER_COUNT = 2
CHUNK_DAYS = 7
MAX_ATTEMPTS = 3
CSV_ENCODING = "utf-8-sig"


def log_to_csv(csv_path, worker_id, attempt, start_date, days, status, message):
    """Append a single log line to the per-worker csv."""
    timestamp = datetime.now().isoformat()
    with open(csv_path, mode="a", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                timestamp,
                worker_id,
                attempt,
                start_date.isoformat(),
                days,
                status,
                message,
            ]
        )


class CsvPrintLogger:
    """Mirror stdout while appending each printed line to the CSV log."""

    def __init__(self, csv_path, worker_id, attempt, start_date, days, original_stdout):
        self.csv_path = csv_path
        self.worker_id = worker_id
        self.attempt = attempt
        self.start_date = start_date
        self.days = days
        self._buffer = ""
        self._original_stdout = original_stdout

    def write(self, data):
        self._original_stdout.write(data)
        self._original_stdout.flush()
        self._buffer += data
        self._flush_buffer_lines()

    def flush(self):
        self._original_stdout.flush()
        self._flush_buffer_lines(flush_remaining=True)

    def _flush_buffer_lines(self, flush_remaining=False):
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                log_to_csv(
                    self.csv_path,
                    self.worker_id,
                    self.attempt,
                    self.start_date,
                    self.days,
                    "print",
                    line,
                )
        if flush_remaining and self._buffer.strip():
            log_to_csv(
                self.csv_path,
                self.worker_id,
                self.attempt,
                self.start_date,
                self.days,
                "print",
                self._buffer.strip(),
            )
            self._buffer = ""


@contextmanager
def capture_prints_to_csv(csv_path, worker_id, attempt, start_date, days):
    """Redirect stdout to also log print lines into CSV."""
    original_stdout = sys.stdout
    logger = CsvPrintLogger(
        csv_path, worker_id, attempt, start_date, days, original_stdout
    )
    sys.stdout = logger
    try:
        yield
    finally:
        logger.flush()
        sys.stdout = original_stdout


def run_parser(worker_id, attempt, start_date, days, csv_path, progress_store):
    """Run parsing for a date range; exceptions bubble up to allow retries."""
    start_str = start_date.isoformat()
    end_str = (start_date + timedelta(days=days - 1)).isoformat()
    with capture_prints_to_csv(csv_path, worker_id, attempt, start_date, days):
        def progress_callback(done, total):
            percent = int(done / total * 100)
            progress_store[worker_id] = (start_date + timedelta(days=done - 1)).isoformat()
            print(f"[parser-{worker_id}] progress {done}/{total} ({percent}%)")

        print(
            f"[parser-{worker_id}] attempt {attempt}: starting range {start_str} -> {end_str}"
        )
        log_to_csv(
            csv_path,
            worker_id,
            attempt,
            start_date,
            days,
            "start",
            f"starting range {start_str} -> {end_str}",
        )

        try:
            options = create_browser_options()
            with get_connection() as conn:
                repo = PostgresPriceRepository(conn)
                with webdriver.Chrome(options=options) as browser:
                    gateway = SeleniumHotelGateway(browser)
                    service = PriceParsingService(repo, gateway)
                    service.parse_period(start_date, days, progress_callback)

            print(
                f"[parser-{worker_id}] attempt {attempt}: finished range {start_str} -> {end_str}"
            )
            log_to_csv(
                csv_path,
                worker_id,
                attempt,
                start_date,
                days,
                "success",
                f"completed range {start_str} -> {end_str}",
            )
        except Exception:
            error_msg = traceback.format_exc()
            print(
                f"[parser-{worker_id}] attempt {attempt}: failed on range {start_str} -> {end_str}\n{error_msg}"
            )
            log_to_csv(
                csv_path,
                worker_id,
                attempt,
                start_date,
                days,
                "error",
                error_msg,
            )
            raise


def start_worker(worker_id, attempt, start_date, days, csv_path, progress_store) -> Process:
    process = Process(
        target=run_parser, args=(worker_id, attempt, start_date, days, csv_path, progress_store)
    )
    process.start()
    return process


def truncate_regular_prices():
    print("[trace] clearing regular_prices table before parsing")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE regular_prices;")
        conn.commit()
    print("[trace] regular_prices cleared")


def ensure_parser_status_table():
    """Создаём таблицу статуса парсера, если её ещё нет."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_parser_status (
                    id INT PRIMARY KEY,
                    started_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    last_completed_date DATE,
                    failed_at DATE,
                    message TEXT
                );
                """
            )
            cur.execute(
                """
                INSERT INTO price_parser_status (id, started_at, status, last_completed_date, failed_at, message)
                VALUES (1, NOW(), 'running', NULL, NULL, NULL)
                ON CONFLICT (id) DO UPDATE SET
                    started_at = EXCLUDED.started_at,
                    status = 'running',
                    last_completed_date = NULL,
                    failed_at = NULL,
                    message = NULL;
                """
            )
        conn.commit()


def update_parser_status(status: str, last_completed_date=None, failed_at=None, message: str | None = None):
    """Обновляем статус прогона парсера (ok / partial / failed)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO price_parser_status (id, started_at, status, last_completed_date, failed_at, message)
                VALUES (1, NOW(), %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_completed_date = EXCLUDED.last_completed_date,
                    failed_at = EXCLUDED.failed_at,
                    message = EXCLUDED.message;
                """,
                (status, last_completed_date, failed_at, message),
            )
        conn.commit()


def run(start_date=None):
    start_ts = time.perf_counter()
    run_id = str(uuid4())
    multiprocessing.set_start_method("spawn", force=True)
    start_date = start_date or datetime.today().date()

    print("[trace] run_price_parser main start")
    print(
        f"[trace] parameters prepared start={start_date}, chunk_days={CHUNK_DAYS}, workers={WORKER_COUNT}"
    )
    log_event(
        level="INFO",
        source="price_parser",
        event="started",
        message=f"start_date={start_date}",
        meta={"start_date": str(start_date), "chunk_days": CHUNK_DAYS, "workers": WORKER_COUNT},
        run_id=run_id,
    )

    ensure_parser_status_table()
    truncate_regular_prices()

    chunks = []
    for idx in range(WORKER_COUNT):
        chunk_start = start_date + timedelta(days=idx * CHUNK_DAYS)
        chunks.append((idx + 1, chunk_start, CHUNK_DAYS))

    csv_paths = {}
    for worker_id, chunk_start, chunk_days in chunks:
        csv_path = os.path.join(ROOT, f"parser_worker_{worker_id}.csv")
        csv_paths[worker_id] = csv_path
        with open(csv_path, mode="w", newline="", encoding=CSV_ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(
                ["timestamp", "worker_id", "attempt", "start_date", "days", "status", "message"]
            )
        print(
            f"[trace] prepared csv log for worker {worker_id} at {csv_path} for range {chunk_start} -> {(chunk_start + timedelta(days=chunk_days - 1)).isoformat()}"
        )

    with Manager() as manager:
        progress_store = manager.dict()
        attempts = {worker_id: 1 for worker_id, _, _ in chunks}
        processes = {
            worker_id: start_worker(
                worker_id, attempts[worker_id], chunk_start, chunk_days, csv_paths[worker_id], progress_store
            )
            for worker_id, chunk_start, chunk_days in chunks
        }

        completed = []
        failed = []

        while processes:
            for worker_id, process in list(processes.items()):
                process.join()
                exit_code = process.exitcode
                if exit_code == 0:
                    print(f"[trace] worker {worker_id} finished successfully")
                    completed.append(worker_id)
                    processes.pop(worker_id, None)
                    continue

                attempts[worker_id] += 1
                if attempts[worker_id] > MAX_ATTEMPTS:
                    print(
                        f"[trace] worker {worker_id} failed after {MAX_ATTEMPTS} attempts; skipping remaining retries"
                    )
                    failed.append(worker_id)
                    processes.pop(worker_id, None)
                    continue

                print(
                    f"[trace] worker {worker_id} crashed with exit_code={exit_code}; restarting attempt {attempts[worker_id]}"
                )
                processes[worker_id] = start_worker(
                    worker_id,
                    attempts[worker_id],
                    next(chunk_start for wid, chunk_start, _ in chunks if wid == worker_id),
                    CHUNK_DAYS,
                    csv_paths[worker_id],
                    progress_store,
                )

        progress_snapshot = {}
        for wid, iso_date in progress_store.items():
            try:
                progress_snapshot[wid] = datetime.fromisoformat(iso_date).date()
            except Exception:
                continue

    last_completed_date = max(progress_snapshot.values()) if progress_snapshot else None

    if failed:
        failure_dates = []
        for worker_id in failed:
            last_done = progress_snapshot.get(worker_id)
            chunk_start = next(chunk_start for wid, chunk_start, _ in chunks if wid == worker_id)
            next_failed_date = (last_done + timedelta(days=1)) if last_done else chunk_start
            failure_dates.append(next_failed_date)

        failed_at = min(failure_dates) if failure_dates else None
        warn_msg = (
            f"Парсер собрал не все данные, сломался на дате {failed_at.isoformat()}"
            if failed_at
            else "Парсер собрал не все данные."
        )
        update_parser_status("partial", last_completed_date, failed_at, warn_msg)
        log_event(
            level="WARNING",
            source="price_parser",
            event="completed",
            message=warn_msg,
            meta={
                "status": "partial",
                "last_completed_date": str(last_completed_date) if last_completed_date else None,
                "failed_at": str(failed_at) if failed_at else None,
                "failed_workers": failed,
            },
            run_id=run_id,
            duration_ms=int((time.perf_counter() - start_ts) * 1000),
        )
    else:
        update_parser_status("ok", last_completed_date, None, None)
        log_event(
            level="INFO",
            source="price_parser",
            event="completed",
            message="status=ok",
            meta={
                "status": "ok",
                "last_completed_date": str(last_completed_date) if last_completed_date else None,
            },
            run_id=run_id,
            duration_ms=int((time.perf_counter() - start_ts) * 1000),
        )

    print(f"[trace] all workers completed; success={completed}, failed={failed}")
    elapsed = time.perf_counter() - start_ts
    print(f"[trace] run_price_parser finished in {elapsed:.2f}s")


if __name__ == "__main__":
    run()
