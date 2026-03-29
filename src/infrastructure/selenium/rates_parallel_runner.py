from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from threading import Lock
from time import perf_counter, sleep
from types import TracebackType

from src.domain.entities.rate import DailyRate
from src.infrastructure.selenium.browser import build_chrome_options
from src.infrastructure.selenium.hotel_rates_gateway import SeleniumHotelRatesGateway
from src.infrastructure.selenium.rates_transform import map_scraped_rates_to_domain


@dataclass(frozen=True, slots=True)
class RatesParallelRunConfig:
    category_to_group: dict[str, str]
    adults_counts: tuple[int, ...]
    days_to_collect: int = 3
    outer_block_size_days: int = 30
    outer_block_pause_seconds: float = 5.0
    date_chunk_size: int = 10
    adults_batch_layout: tuple[tuple[int, ...], ...] = ((1, 2, 3), (4, 5, 6))
    headless: bool = True
    wait_seconds: int = 20
    batch_pause_seconds: float = 3.0
    retry_count: int = 1
    retry_pause_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class ParserRunOutcome:
    adults_count: int
    rates: tuple[DailyRate, ...]
    stay_date: date | None = None
    days_count: int = 1
    total_found: int = 0
    total_collected: int = 0
    failed_fn: str | None = None
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class AggregatedStats:
    adults_count: int
    total_days: int
    success_days: int
    failed_days: int
    total_found: int
    total_collected: int
    total_elapsed_seconds: float
    errors: tuple[tuple[date | None, str], ...]


def build_stay_dates(start_date: date, days_to_collect: int) -> list[date]:
    if days_to_collect <= 0:
        raise ValueError("days_to_collect must be > 0")
    return [start_date + timedelta(days=offset) for offset in range(days_to_collect)]


def split_stay_dates_into_outer_blocks(stay_dates: list[date], block_size: int) -> list[list[date]]:
    if block_size <= 0:
        raise ValueError("block_size must be > 0")
    return [stay_dates[idx:idx + block_size] for idx in range(0, len(stay_dates), block_size)]


def split_stay_dates_into_chunks(stay_dates: list[date], chunk_size: int) -> list[list[date]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    return [stay_dates[idx:idx + chunk_size] for idx in range(0, len(stay_dates), chunk_size)]


class SeleniumRatesParallelRunner:
    def __init__(self, config: RatesParallelRunConfig):
        if not config.category_to_group:
            raise ValueError("category_to_group must not be empty; seed category_rules in Postgres first")
        if not config.adults_counts:
            raise ValueError("adults_counts must not be empty")
        for adults in config.adults_counts:
            if adults <= 0:
                raise ValueError("adults_counts must contain only positive values")
        if config.outer_block_size_days <= 0:
            raise ValueError("outer_block_size_days must be > 0")
        if config.outer_block_pause_seconds < 0:
            raise ValueError("outer_block_pause_seconds must be >= 0")
        if config.date_chunk_size <= 0:
            raise ValueError("date_chunk_size must be > 0")
        if config.batch_pause_seconds < 0:
            raise ValueError("batch_pause_seconds must be >= 0")
        if config.retry_count < 0:
            raise ValueError("retry_count must be >= 0")
        if config.retry_pause_seconds < 0:
            raise ValueError("retry_pause_seconds must be >= 0")
        if config.adults_batch_layout:
            configured_adults = {value for batch in config.adults_batch_layout for value in batch}
            unexpected = configured_adults.difference(config.adults_counts)
            if unexpected:
                raise ValueError("adults_batch_layout contains values not present in adults_counts")
        self._config = config
        self._log_lock = Lock()

    def run(self, *, start_date: date) -> list[DailyRate]:
        run_started_at = perf_counter()
        try:
            from selenium import webdriver
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "Selenium is required for parallel rates runner. Install `selenium` and ChromeDriver."
            ) from exc

        stay_dates = build_stay_dates(start_date, self._config.days_to_collect)
        outer_blocks = split_stay_dates_into_outer_blocks(stay_dates, self._config.outer_block_size_days)
        out: list[DailyRate] = []
        outcomes: list[ParserRunOutcome] = []
        days_total = len(stay_dates)
        blocks_total = len(outer_blocks)

        for block_index, outer_block_dates in enumerate(outer_blocks, start=1):
            block_start_day_index = ((block_index - 1) * self._config.outer_block_size_days) + 1
            block_end_day_index = block_start_day_index + len(outer_block_dates) - 1
            self._log(
                f"[БЛОК {block_index}/{blocks_total}] старт — дни {block_start_day_index}-{block_end_day_index} из {days_total}"
            )
            date_chunks = split_stay_dates_into_chunks(outer_block_dates, self._config.date_chunk_size)
            chunks_total = len(date_chunks)

            for chunk_index, stay_dates_chunk in enumerate(date_chunks, start=1):
                chunk_start_day_index = block_start_day_index + ((chunk_index - 1) * self._config.date_chunk_size)
                chunk_end_day_index = chunk_start_day_index + len(stay_dates_chunk) - 1
                self._log(
                    f"[ЧАНК {chunk_index}/{chunks_total}] старт — [БЛОК {block_index}/{blocks_total}] "
                    f"дни {chunk_start_day_index}-{chunk_end_day_index} из {days_total}"
                )
                adults_batches = self._adults_batches()
                for batch_index, adults_batch in enumerate(adults_batches, start=1):
                    batch_label = self._format_batch_label(adults_batch)
                    self._log(
                        f"[БАТЧ {batch_label}] старт — [БЛОК {block_index}/{blocks_total}] [ЧАНК {chunk_index}/{chunks_total}] "
                        f"дни {chunk_start_day_index}-{chunk_end_day_index} из {days_total}"
                    )
                    batch_outcomes = self._run_batch(
                        webdriver=webdriver,
                        category_to_group=self._config.category_to_group,
                        adults_counts=adults_batch,
                        stay_dates=stay_dates_chunk,
                        day_numbering=(chunk_start_day_index, days_total),
                        chunk_numbering=(chunk_index, chunks_total),
                    )
                    outcomes.extend(batch_outcomes)
                    for outcome in batch_outcomes:
                        out.extend(outcome.rates)
                    self._log(
                        f"[БАТЧ {batch_label}] завершён — [БЛОК {block_index}/{blocks_total}] [ЧАНК {chunk_index}/{chunks_total}] "
                        f"дни {chunk_start_day_index}-{chunk_end_day_index} из {days_total}"
                    )
                    if batch_index < len(adults_batches) and self._config.batch_pause_seconds > 0:
                        sleep(self._config.batch_pause_seconds)
                self._log(
                    f"[ЧАНК {chunk_index}/{chunks_total}] завершён — [БЛОК {block_index}/{blocks_total}] "
                    f"дни {chunk_start_day_index}-{chunk_end_day_index} из {days_total}"
                )

            self._log(f"[БЛОК {block_index}/{blocks_total}] завершён")
            if block_index < blocks_total and self._config.outer_block_pause_seconds > 0:
                sleep(self._config.outer_block_pause_seconds)

        total_elapsed = self._format_duration(perf_counter() - run_started_at)
        self._log(f"Парсинг категорий закончен, общее время {total_elapsed}")
        aggregated_stats = self._aggregate_outcomes_by_adults(outcomes)
        success_count = sum(1 for x in aggregated_stats if x.failed_days == 0)
        self._log(
            f"из {len(self._config.adults_counts)} парсеров "
            f"{success_count} успешно выполнили работу"
        )
        self._log("")
        for stats in aggregated_stats:
            self._log(f"парсер ({self._adults_label(stats.adults_count)}):")
            self._log(f"- успешно: {stats.success_days}/{stats.total_days} дней")
            if stats.failed_days:
                self._log(f"- ошибок: {stats.failed_days}")
            self._log(f"- найдено: {stats.total_found}")
            self._log(f"- собрано: {stats.total_collected}")
            self._log(f"- время: {self._format_duration(stats.total_elapsed_seconds)}")
            if stats.errors:
                self._log("- ошибки:")
                for failed_date, fn_name in stats.errors:
                    date_label = failed_date.strftime("%d.%m.%y") if failed_date is not None else "?"
                    self._log(f"  • {date_label} -> {fn_name}")

        return out

    def _run_batch(
        self,
        *,
        webdriver,
        category_to_group: dict[str, str],
        adults_counts: tuple[int, ...],
        stay_dates: list[date],
        day_numbering: tuple[int, int] | None = None,
        chunk_numbering: tuple[int, int] | None = None,
    ) -> list[ParserRunOutcome]:
        outcomes: list[ParserRunOutcome] = []
        with ThreadPoolExecutor(max_workers=len(adults_counts)) as pool:
            future_to_adults = {
                pool.submit(
                    self._run_single_parser_with_retry,
                    webdriver=webdriver,
                    category_to_group=category_to_group,
                    adults_count=adults_count,
                    stay_dates=stay_dates,
                    day_numbering=day_numbering,
                    chunk_numbering=chunk_numbering,
                ): adults_count
                for adults_count in adults_counts
            }
            for future in as_completed(future_to_adults):
                adults_count = future_to_adults[future]
                try:
                    outcome = future.result()
                except Exception as exc:
                    fn_name = self._extract_fn_name(exc.__traceback__)
                    outcome = ParserRunOutcome(
                        adults_count=adults_count,
                        rates=tuple(),
                        stay_date=stay_dates[0] if stay_dates else None,
                        days_count=len(stay_dates),
                        total_found=0,
                        total_collected=0,
                        failed_fn=fn_name,
                        elapsed_seconds=0.0,
                    )
                    msg = self._short_error_text(exc)
                    log_day_index, log_days_total = day_numbering or (1, len(stay_dates))
                    chunk_text = self._format_chunk_log_suffix(chunk_numbering)
                    self._log(
                        f"ОШИБКА, парсер ({self._adults_label(adults_count)}), "
                        f"({log_day_index} день из {log_days_total}){chunk_text} {fn_name}, {msg}"
                    )
                outcomes.append(outcome)
        return outcomes

    def _run_single_parser_with_retry(
        self,
        *,
        webdriver,
        category_to_group: dict[str, str],
        adults_count: int,
        stay_dates: list[date],
        day_numbering: tuple[int, int] | None = None,
        chunk_numbering: tuple[int, int] | None = None,
    ) -> ParserRunOutcome:
        total_attempts = self._config.retry_count + 1
        final_outcome: ParserRunOutcome | None = None
        log_day_index, log_days_total = day_numbering or (1, len(stay_dates))

        for attempt in range(1, total_attempts + 1):
            outcome = self._run_single_parser(
                webdriver=webdriver,
                category_to_group=category_to_group,
                adults_count=adults_count,
                stay_dates=stay_dates,
                day_numbering=day_numbering,
                chunk_numbering=chunk_numbering,
            )
            if outcome.failed_fn is None:
                return outcome
            final_outcome = outcome
            if attempt >= total_attempts:
                break
            chunk_text = self._format_chunk_retry(chunk_numbering)
            self._log(
                f"[RETRY] парсер ({self._adults_label(adults_count)}), "
                f"{chunk_text} ({log_day_index} день из {log_days_total}), "
                f"попытка {attempt + 1}/{total_attempts}"
            )
            if self._config.retry_pause_seconds > 0:
                sleep(self._config.retry_pause_seconds)

        if final_outcome is None:
            raise RuntimeError("retry wrapper finished without outcome")
        return ParserRunOutcome(
            adults_count=final_outcome.adults_count,
            rates=tuple(),
            stay_date=final_outcome.stay_date,
            days_count=final_outcome.days_count,
            total_found=final_outcome.total_found,
            total_collected=final_outcome.total_collected,
            failed_fn=final_outcome.failed_fn,
            elapsed_seconds=final_outcome.elapsed_seconds,
        )

    def _run_single_parser(
        self,
        *,
        webdriver,
        category_to_group: dict[str, str],
        adults_count: int,
        stay_dates: list[date],
        day_numbering: tuple[int, int] | None = None,
        chunk_numbering: tuple[int, int] | None = None,
    ) -> ParserRunOutcome:
        adults_label = self._adults_label(adults_count)
        days_total = len(stay_dates)
        start_day_index = 1
        log_days_total = days_total
        if day_numbering is not None:
            start_day_index, log_days_total = day_numbering
        parser_started_at = perf_counter()

        self._log(f"парсер ({adults_label}) начал работу")
        parsed: list[DailyRate] = []
        failed_fn: str | None = None
        totals = {"found": 0, "collected": 0}
        try:
            options = build_chrome_options(headless=self._config.headless)
            with webdriver.Chrome(options=options) as browser:
                try:
                    gateway = SeleniumHotelRatesGateway(
                        browser,
                        adults_count=adults_count,
                        wait_seconds=self._config.wait_seconds,
                    )
                except Exception as exc:
                    fn_name = self._extract_fn_name(exc.__traceback__)
                    msg = self._short_error_text(exc)
                    chunk_text = self._format_chunk_log_suffix(chunk_numbering)
                    self._log(
                        f"ОШИБКА, парсер ({adults_label}), "
                        f"({start_day_index} день из {log_days_total}){chunk_text} {fn_name}, {msg}"
                    )
                    failed_fn = fn_name
                    return ParserRunOutcome(
                        adults_count=adults_count,
                        rates=tuple(parsed),
                        stay_date=stay_dates[0] if stay_dates else None,
                        days_count=len(stay_dates),
                        total_found=totals["found"],
                        total_collected=totals["collected"],
                        failed_fn=failed_fn,
                        elapsed_seconds=perf_counter() - parser_started_at,
                    )
                for local_day_index, stay_date in enumerate(stay_dates, start=1):
                    log_day_index = start_day_index + local_day_index - 1
                    try:
                        self._install_day_logging_hooks(
                            gateway=gateway,
                            adults_label=adults_label,
                            day_index=log_day_index,
                            days_total=log_days_total,
                            stay_date=stay_date,
                            totals=totals,
                        )
                        scraped = gateway.get_rates_for_date(stay_date)
                        parsed.extend(
                            map_scraped_rates_to_domain(
                                scraped,
                                category_to_group=self._config.category_to_group,
                                adults_counts=[adults_count],
                            )
                        )
                    except Exception as exc:
                        fn_name = self._extract_fn_name(exc.__traceback__)
                        if failed_fn is None:
                            failed_fn = fn_name
                        msg = self._short_error_text(exc)
                        chunk_text = self._format_chunk_log_suffix(chunk_numbering)
                        self._log(
                            f"ОШИБКА, парсер ({adults_label}), ({log_day_index} день из {log_days_total}){chunk_text} "
                            f"{fn_name}, {msg}"
                        )
        finally:
            self._log(f"парсер ({adults_label}) закончил работу")

        return ParserRunOutcome(
            adults_count=adults_count,
            rates=tuple(parsed),
            stay_date=stay_dates[0] if stay_dates else None,
            days_count=len(stay_dates),
            total_found=totals["found"],
            total_collected=totals["collected"],
            failed_fn=failed_fn,
            elapsed_seconds=perf_counter() - parser_started_at,
        )

    def _install_day_logging_hooks(
        self,
        *,
        gateway: SeleniumHotelRatesGateway,
        adults_label: str,
        day_index: int,
        days_total: int,
        stay_date: date,
        totals: dict[str, int],
    ) -> None:
        original_find_categories = SeleniumHotelRatesGateway._find_categories.__get__(gateway, SeleniumHotelRatesGateway)
        original_extract_rate = SeleniumHotelRatesGateway._extract_current_category_rate.__get__(
            gateway, SeleniumHotelRatesGateway
        )

        state = {"total": None, "collected": 0}
        date_label = stay_date.strftime("%d.%m.%y")

        def logged_find_categories():
            categories = original_find_categories()
            if state["total"] is None:
                state["total"] = len(categories)
                totals["found"] += state["total"]
                self._log(
                    f"парсер ({adults_label}), ({day_index} день из {days_total}) "
                    f"нашел {state['total']} категорий на дату {date_label}"
                )
            return categories

        def logged_extract_rate(*args, **kwargs):
            item = original_extract_rate(*args, **kwargs)
            if item is not None:
                state["collected"] += 1
                totals["collected"] += 1
                total = state["total"] if state["total"] is not None else "?"
                self._log(
                    f"парсер ({adults_label}), ({day_index} день из {days_total}), "
                    f"собрал данные {state['collected']} категории из {total} на дату {date_label}"
                )
            return item

        gateway._find_categories = logged_find_categories
        gateway._extract_current_category_rate = logged_extract_rate

    def _log(self, message: str) -> None:
        with self._log_lock:
            print(message)

    def _adults_batches(self) -> list[tuple[int, ...]]:
        if self._config.adults_batch_layout:
            allowed = set(self._config.adults_counts)
            batches = []
            for batch in self._config.adults_batch_layout:
                filtered = tuple(value for value in batch if value in allowed)
                if filtered:
                    batches.append(filtered)
            if batches:
                return batches
        adults = tuple(self._config.adults_counts)
        return [adults[idx:idx + 3] for idx in range(0, len(adults), 3)]

    @staticmethod
    def _format_batch_label(adults_counts: tuple[int, ...]) -> str:
        return ",".join(str(value) for value in adults_counts)

    @staticmethod
    def _format_chunk_log_suffix(chunk_numbering: tuple[int, int] | None) -> str:
        if chunk_numbering is None:
            return ""
        chunk_index, chunks_total = chunk_numbering
        return f", чанк {chunk_index}/{chunks_total}"

    @staticmethod
    def _format_chunk_retry(chunk_numbering: tuple[int, int] | None) -> str:
        if chunk_numbering is None:
            return ""
        chunk_index, chunks_total = chunk_numbering
        return f"чанк {chunk_index}/{chunks_total},"

    def _aggregate_outcomes_by_adults(self, outcomes: list[ParserRunOutcome]) -> list[AggregatedStats]:
        by_adults: dict[int, dict[str, object]] = {}
        for outcome in outcomes:
            current = by_adults.setdefault(
                outcome.adults_count,
                {
                    "total_days": 0,
                    "success_days": 0,
                    "failed_days": 0,
                    "total_found": 0,
                    "total_collected": 0,
                    "total_elapsed_seconds": 0.0,
                    "errors": [],
                },
            )
            current["total_days"] = int(current["total_days"]) + outcome.days_count
            current["total_found"] = int(current["total_found"]) + outcome.total_found
            current["total_collected"] = int(current["total_collected"]) + outcome.total_collected
            current["total_elapsed_seconds"] = float(current["total_elapsed_seconds"]) + outcome.elapsed_seconds
            if outcome.failed_fn is None:
                current["success_days"] = int(current["success_days"]) + outcome.days_count
            else:
                current["failed_days"] = int(current["failed_days"]) + outcome.days_count
                errors = list(current["errors"])
                errors.append((outcome.stay_date, outcome.failed_fn))
                current["errors"] = errors
        return [
            AggregatedStats(
                adults_count=adults_count,
                total_days=int(stats["total_days"]),
                success_days=int(stats["success_days"]),
                failed_days=int(stats["failed_days"]),
                total_found=int(stats["total_found"]),
                total_collected=int(stats["total_collected"]),
                total_elapsed_seconds=float(stats["total_elapsed_seconds"]),
                errors=tuple(stats["errors"]),
            )
            for adults_count, stats in sorted(by_adults.items())
        ]

    @staticmethod
    def _adults_label(adults_count: int) -> str:
        if adults_count == 1:
            return "1 взрослый"
        return f"{adults_count} взрослых"

    @staticmethod
    def _extract_fn_name(traceback: TracebackType | None) -> str:
        if traceback is None:
            return "<unknown>"
        current = traceback
        while current.tb_next is not None:
            current = current.tb_next
        return current.tb_frame.f_code.co_name

    @staticmethod
    def _short_error_text(exc: Exception) -> str:
        text = str(exc).strip()
        if not text:
            return "<empty error>"
        first_line = text.splitlines()[0].strip()
        if first_line.startswith("Message:"):
            return first_line
        return f"Message: {first_line}"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours} час. {minutes} мин. {secs} сек."
