from datetime import date, datetime
from typing import ClassVar

from pandas import DataFrame, DatetimeIndex, Timedelta, Timestamp, date_range

from mt.data.asset import Asset
from mt.rules.sections import AllocationBaaSection
from mt.rules.shared import settings

from .base import ranked
from .monthly import Monthly


FAST_WEIGHTS = {1: 12.0, 3: 4.0, 6: 2.0, 12: 1.0}
SLOW_MONTHS = 12
MONTH_END_GAP_DAYS = 7


def month_end_closes(frame: DataFrame, month_start: date, months: int) -> list[float] | None:
    days = DatetimeIndex(frame.index).tz_localize(None).normalize()
    cutoffs = date_range(
        end=Timestamp(month_start) - Timedelta(days=1), periods=months + 1, freq="ME"
    )[::-1]
    positions = days.get_indexer(cutoffs, method="pad")
    if (positions < 0).any() or (
        cutoffs - days[positions] > Timedelta(days=MONTH_END_GAP_DAYS)
    ).any():
        return None
    return frame["close"].iloc[positions].astype(float).tolist()


def fast_momentum(closes: list[float]) -> float:
    weighted = sum(
        weight * (closes[0] / closes[months] - 1) for months, weight in FAST_WEIGHTS.items()
    )
    return weighted / len(FAST_WEIGHTS)


def slow_momentum(closes: list[float]) -> float:
    return closes[0] / (sum(closes[: SLOW_MONTHS + 1]) / (SLOW_MONTHS + 1)) - 1


class Allocation(Monthly):
    rules: ClassVar[AllocationBaaSection]

    @classmethod
    def symbols(cls) -> tuple[str, ...]:
        rules = cls.rules
        found = (*rules.canary_symbols, *rules.offensive_symbols, *rules.defensive_symbols)
        return tuple(dict.fromkeys((*found, rules.cash_symbol)))

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
            symbol
            for symbol in (*self.rules.canary_symbols, self.rules.cash_symbol)
            if symbol not in fast
        ]
        if missing:
            self.portfolio.record(
                self,
                f"select.unread.{day}",
                "warning",
                f"{self.name()} cannot rebalance: no 13 months of closes for {', '.join(missing)}",
            )
            return None
        falling = sum(1 for symbol in self.rules.canary_symbols if fast[symbol] < 0)
        is_defensive = falling >= self.rules.breadth
        if is_defensive:
            top = ranked(
                (symbol for symbol in self.rules.defensive_symbols if symbol in slow),
                symbol=lambda symbol: symbol,
                score=lambda symbol: slow[symbol],
            )[: self.rules.defensive_top]
            floor = slow[self.rules.cash_symbol]
            chosen = [symbol if slow[symbol] >= floor else self.rules.cash_symbol for symbol in top]
        else:
            chosen = ranked(
                (symbol for symbol in self.rules.offensive_symbols if symbol in slow),
                symbol=lambda symbol: symbol,
                score=lambda symbol: slow[symbol],
            )[: self.rules.offensive_top]
        picks = tuple(Asset.from_symbol(symbol) for symbol in dict.fromkeys(chosen))
        self.portfolio.record(
            self,
            f"select.read.{day}",
            "info",
            f"{self.name()} is {'defensive' if is_defensive else 'offensive'} "
            f"({falling} of {len(self.rules.canary_symbols)} canaries falling): "
            f"holding {', '.join(map(str, picks))}",
        )
        return picks


class AllocationBaa(Allocation):
    key = "allocation_baa"
    code = "b"
    rules: ClassVar[AllocationBaaSection] = settings.allocation_baa
    entry_minutes = rules.entry_minutes
    stop_fraction = rules.stop_fraction
    holdings_max = rules.holdings_max
    is_paused = rules.is_paused
