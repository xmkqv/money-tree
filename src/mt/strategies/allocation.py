from datetime import date, datetime, timedelta
from typing import Any, ClassVar, cast

from pandas import DataFrame, DateOffset, DatetimeIndex, Timestamp

from mt.data.asset import Asset

from .monthly import Monthly


FAST_WEIGHTS = {1: 12.0, 3: 4.0, 6: 2.0, 12: 1.0}
SLOW_MONTHS = 12
MONTH_END_GAP_DAYS = 7


def month_end_closes(frame: DataFrame, month_start: date, months: int) -> list[float] | None:
    dates = cast(Any, cast(DatetimeIndex, frame.index)).date
    closes: list[float] = []
    for offset in range(months + 1):
        cutoff = (Timestamp(month_start) - DateOffset(months=offset) - timedelta(days=1)).date()
        eligible = frame["close"][dates <= cutoff]
        if eligible.empty:
            return None
        if (cutoff - cast(Timestamp, eligible.index[-1]).date()).days > MONTH_END_GAP_DAYS:
            return None
        closes.append(float(eligible.iloc[-1]))
    return closes


def fast_momentum(closes: list[float]) -> float:
    weighted = sum(
        weight * (closes[0] / closes[months] - 1) for months, weight in FAST_WEIGHTS.items()
    )
    return weighted / len(FAST_WEIGHTS)


def slow_momentum(closes: list[float]) -> float:
    return closes[0] / (sum(closes[: SLOW_MONTHS + 1]) / (SLOW_MONTHS + 1)) - 1


class Allocation(Monthly):
    canary_symbols: ClassVar[tuple[str, ...]]
    offensive_symbols: ClassVar[tuple[str, ...]]
    defensive_symbols: ClassVar[tuple[str, ...]]
    cash_symbol: ClassVar[str]
    offensive_top: ClassVar[int]
    defensive_top: ClassVar[int]
    breadth: ClassVar[int]

    @classmethod
    def symbols(cls) -> tuple[str, ...]:
        found = (*cls.canary_symbols, *cls.offensive_symbols, *cls.defensive_symbols)
        return tuple(dict.fromkeys((*found, cls.cash_symbol)))

    def select(self, now: datetime) -> tuple[Asset, ...] | None:
        day = now.date()
        month_start = day.replace(day=1)
        fast: dict[str, float] = {}
        slow: dict[str, float] = {}
        for symbol in self.symbols():
            frame = self.portfolio.daily_frame(Asset.from_symbol(symbol))
            closes = None if frame is None else month_end_closes(frame, month_start, SLOW_MONTHS)
            if closes is None:
                continue
            fast[symbol] = fast_momentum(closes)
            slow[symbol] = slow_momentum(closes)
        missing = [
            symbol for symbol in (*self.canary_symbols, self.cash_symbol) if symbol not in fast
        ]
        if missing:
            self.portfolio.record(
                self,
                f"select.unread.{day}",
                "warning",
                f"{self.name()} cannot rebalance: no 13 months of closes for {', '.join(missing)}",
            )
            return None
        falling = sum(1 for symbol in self.canary_symbols if fast[symbol] < 0)
        is_defensive = falling >= self.breadth
        if is_defensive:
            ranked = self._ranked(self.defensive_symbols, slow)[: self.defensive_top]
            floor = slow[self.cash_symbol]
            chosen = [symbol if slow[symbol] >= floor else self.cash_symbol for symbol in ranked]
        else:
            chosen = self._ranked(self.offensive_symbols, slow)[: self.offensive_top]
        picks = tuple(Asset.from_symbol(symbol) for symbol in dict.fromkeys(chosen))
        self.portfolio.record(
            self,
            f"select.read.{day}",
            "info",
            f"{self.name()} is {'defensive' if is_defensive else 'offensive'} "
            f"({falling} of {len(self.canary_symbols)} canaries falling): "
            f"holding {', '.join(map(str, picks))}",
        )
        return picks

    @staticmethod
    def _ranked(symbols: tuple[str, ...], momentum: dict[str, float]) -> list[str]:
        found = (symbol for symbol in symbols if symbol in momentum)
        return sorted(found, key=lambda symbol: (-momentum[symbol], symbol))


class AllocationBaa(Allocation):
    key = "allocation_baa"
    code = "b"
