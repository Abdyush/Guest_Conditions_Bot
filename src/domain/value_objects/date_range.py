from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


class DateRangeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DateRange:
    """
    Полуинтервал проживания: [start, end)
    start — дата заезда (первая ночь)
    end   — дата выезда (не включается), т.е. last_night = end - 1 day
    """
    start: date
    end: date

    def __post_init__(self) -> None:
        if not isinstance(self.start, date) or not isinstance(self.end, date):
            raise DateRangeError("start/end must be datetime.date")
        if self.end <= self.start:
            raise DateRangeError("end must be after start (end is checkout day)")

    @property
    def nights(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start <= d < self.end

    def overlaps(self, other: DateRange) -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: DateRange) -> DateRange | None:
        if not self.overlaps(other):
            return None
        s = max(self.start, other.start)
        e = min(self.end, other.end)
        # s < e гарантировано overlaps'ом
        return DateRange(s, e)

    def iter_nights(self) -> list[date]:
        """
        Список дат ночёвок: start, start+1, ..., end-1
        """
        out: list[date] = []
        cur = self.start
        while cur < self.end:
            out.append(cur)
            cur += timedelta(days=1)
        return out