"""time_budget.py — Plan 1. 크롤러 전체 · 하위 단계별 남은 예산 추적.

`TimeBudget(total=180.0)` 로 초기화 후 하위 호출에 `tb.remaining()` 를 전파.
초과 시 `tb.check()` 는 `TimeBudgetExpired` 를 raise — 호출부가 partial result 로 early return.
"""
from __future__ import annotations

import time


class TimeBudgetExpired(Exception):
    pass


class TimeBudget:

    def __init__(self, total: float):
        self.total = float(total)
        self.start = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def remaining(self) -> float:
        return max(0.0, self.total - self.elapsed())

    def expired(self) -> bool:
        return self.elapsed() >= self.total

    def check(self) -> None:
        if self.expired():
            raise TimeBudgetExpired(
                f"time budget exceeded: {self.elapsed():.1f}s >= {self.total:.1f}s"
            )

    def sub(self, fraction: float) -> float:
        """남은 시간의 fraction(0~1)만큼을 하위 호출의 timeout 인자로 돌려준다."""
        return max(0.0, self.remaining() * max(0.0, min(1.0, fraction)))
