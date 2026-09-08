from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import accumulate
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.config.settings import settings
from mt.config.values import StrategyKey
from mt.exchange import TRADING_ZONE
from mt.frames import frame_between, frame_since, frame_until, regular_session
from mt.indicators import latest_atr, latest_turnover_usd
from mt.position import Direction, next_stop

from .base import Candidate, Holding, Ladder, Portfolio, Session, Strategy, family_keys, ranked


@dataclass(frozen=True, slots=True)
class RangeMarks:
    high: float
    mid: float
    low: float


@dataclass(frozen=True, slots=True)
class Break:
    symbol: str
    direction: Direction
    high: float
    low: float
    close: float
    signal_at: Timestamp


def range_level(high: float, low: float, fraction: float) -> float:
    return low + (high - low) * fraction


def range_marks(high: float, low: float) -> RangeMarks:
    return RangeMarks(high, range_level(high, low, settings.breakout.mid_fraction), low)


def range_stop(direction: Direction, high: float, low: float) -> float:
    breakout = settings.breakout
    fraction = breakout.long_stop_fraction if direction == 1 else breakout.short_stop_fraction
    return range_level(high, low, fraction)


def range_break(high: float, low: float, close: float) -> Direction | None:
    if not all(isfinite(value) for value in (high, low, close)):
        return None
    return 1 if close > high else -1 if close < low else None


def is_setup_ready(high: float, low: float, close: float) -> bool:
    direction = range_break(high, low, close)
    if direction is None:
        return False
    if high - low < settings.breakout.range_fraction_min * close:
        return False
    fraction = abs(close - range_stop(direction, high, low)) / close
    return settings.breakout.stop_fraction_min <= fraction <= settings.breakout.stop_fraction_max


def session_volume(frame: DataFrame, day: date, clock: time) -> float | None:
    sessions = settings.breakout.past_sessions
    regular = regular_session(frame)
    index = cast(DatetimeIndex, regular.index)
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
    volume = regular["volume"]
    aggregates = DataFrame(
        {
            "session_date": session_dates,
            "cumulative_volume": cast(
                Series,
                cast(Any, volume).where(pandas_index.time <= clock, 0.0),
            ),
        },
        index=index,
    )
    columns = ["cumulative_volume"]
    relevant = cast(Any, session_dates) <= current_session
    grouped = cast(
        DataFrame,
        cast(Any, aggregates).loc[relevant].groupby("session_date", sort=True)[columns].sum(),
    )
    if current_session not in grouped.index:
        return None
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    past = cast(
        DataFrame,
        cast(Any, grouped).loc[grouped_index < current_session].tail(sessions),
    )
    if len(past) != sessions:
        return None
    clock_average = float(cast(Any, past["cumulative_volume"]).mean())
    current = float(cast(Any, grouped).loc[current_session, "cumulative_volume"])
    if not all(isfinite(value) for value in (clock_average, current)):
        return None
    if clock_average <= 0:
        return None
    return current / clock_average


def is_relative_volume_ready(frame: DataFrame, day: date, clock: time, multiple: float) -> bool:
    if frame.empty:
        return False
    ratio = session_volume(frame, day, clock)
    return ratio is not None and ratio >= multiple


class Breakout(Strategy):
    is_stop_resting = True
    positions_max = settings.breakout.positions_max
    opening_minutes: ClassVar[int]
    volume_multiple: ClassVar[float]
    target_multiples: ClassVar[tuple[float, float, float]]
    entry_extension_max: ClassVar[float | None]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._scanned: set[str] = set()
        self._past_failed_at: date | None = None

    @classmethod
    def cap_keys(cls) -> frozenset[StrategyKey]:
        return family_keys(cls.family)

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return (
            opens + timedelta(minutes=cls.opening_minutes),
            opens + timedelta(minutes=settings.breakout.scan_minutes),
        )

    @classmethod
    def target_prices(
        cls, entry: float, stop: float, direction: Direction
    ) -> tuple[float, float, float]:
        risk = abs(entry - stop)
        first, second, third = cls.target_multiples
        return (
            entry + direction * risk * first,
            entry + direction * risk * second,
            entry + direction * risk * third,
        )

    def begin(self, day: date) -> None:
        self._scanned.clear()

    def ladder(self, holding: Holding, original: float, remaining: float) -> Ladder | None:
        fraction = remaining / original if original else 1.0
        closed = accumulate(settings.breakout.target_fractions[:-1])
        stage = sum(fraction <= 1.0 - sold for sold in closed)
        targets = self.target_prices(holding.entry, holding.stop, holding.direction)
        return Ladder(original, targets, stage)

    def run(self, session: Session) -> None:
        now = session.now
        opening_end, scan_end = self.entry_window(session.opens, session.closes)
        if now.minute % self.opening_minutes or not opening_end <= now <= scan_end:
            return
        if not self.portfolio.market_symbols():
            return
        if self.is_capped():
            self.portfolio.record(
                self,
                f"entries.capped.{now.date()}",
                "info",
                f"{self.family.capitalize()} entries paused: "
                f"{self.positions_max} positions already open",
            )
            return
        symbols = self._unscanned(now.date())
        if not symbols or self._past_failed_at == now.date():
            return
        try:
            frames = self.portfolio.minute_frames(symbols, session.opens, now, self.opening_minutes)
        except Exception as error:
            self._stand_down(now.date(), error)
            return
        breaks = self._breaks(frames, session, opening_end)
        if not breaks:
            return
        breaks = ranked(
            breaks,
            symbol=lambda found: found.symbol,
            turnover=lambda found: self._turnover(found.symbol, now),
        )
        try:
            histories = self.portfolio.minute_frames(
                [found.symbol for found in breaks],
                now - timedelta(days=settings.breakout.confirm_past_days),
                now,
                self.opening_minutes,
            )
        except Exception as error:
            self._stand_down(now.date(), error)
            return
        for found in breaks:
            if self.is_capped():
                return
            frame = histories.get(found.symbol)
            if frame is None:
                continue
            if not self.is_confirmed(frame_until(frame, found.signal_at), now):
                continue
            price = self._price(found)
            if self.is_overextended(found, price):
                self.portfolio.record(
                    self,
                    f"entry.overextended.{found.symbol}.{now.date()}",
                    "warning",
                    f"{found.symbol} entry skipped: price is more than "
                    f"{self.entry_extension_max:g} times the opening range size beyond "
                    "the breakout level",
                )
                continue
            stop = range_stop(found.direction, found.high, found.low)
            self.portfolio.enter(
                self, Candidate(found.symbol, price, stop, found.direction), session
            )

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if now >= session.closes - timedelta(minutes=settings.breakout.close_lead_minutes):
            self.portfolio.exit(holding)
            return
        price = self.portfolio.last_price(holding.symbol)
        holding.highest = max(holding.highest, price)
        holding.lowest = min(holding.lowest, price)
        ladder = holding.ladder
        if ladder is None:
            return
        reached = (
            price >= ladder.targets[ladder.stage]
            if holding.direction == 1
            else price <= ladder.targets[ladder.stage]
        )
        if reached:
            fractions = settings.breakout.target_fractions
            if ladder.stage == len(fractions) - 1:
                self.portfolio.exit(holding)
                return
            quantity = ladder.original_quantity * fractions[ladder.stage]
            ladder.stage += 1
            self.portfolio.exit(holding, quantity)
            return
        if ladder.stage == 0:
            return
        try:
            recent = self.portfolio.minute_frames(
                [holding.symbol],
                now - timedelta(days=settings.breakout.trail_past_days),
                now,
                self.opening_minutes,
            ).get(holding.symbol)
        except Exception as error:
            self.portfolio.record(
                self,
                f"trail.stalled.{holding.symbol}.{now.date()}",
                "warning",
                f"{holding.symbol} trailing stop not updated: {type(error).__name__}",
            )
            return
        if recent is None:
            return
        frame = regular_session(recent)
        if len(frame) < settings.breakout.trail_candles_min:
            return
        trail = settings.breakout.trail_atr_multiple * latest_atr(frame, settings.indicators.period)
        candidate = (
            max(holding.entry, holding.highest - trail)
            if holding.direction == 1
            else min(holding.entry, holding.lowest + trail)
        )
        holding.stop = next_stop(holding.direction, holding.stop, candidate)
        self.portfolio.protect(holding)

    def is_confirmed(self, frame: DataFrame, now: datetime) -> bool:
        if frame.empty:
            return False
        return is_relative_volume_ready(
            frame,
            now.date(),
            cast(Timestamp, frame.index[-1]).time(),
            self.volume_multiple,
        )

    def is_overextended(self, found: Break, price: float) -> bool:
        limit = self.entry_extension_max
        if limit is None:
            return False
        span = found.high - found.low
        if found.direction == 1:
            return price > found.high + limit * span
        return price < found.low - limit * span

    def _unscanned(self, day: date) -> list[str]:
        return [
            symbol
            for symbol in self.portfolio.market_symbols()
            if symbol not in self._scanned and not self.portfolio.is_taken(self, symbol, day)
        ]

    def _turnover(self, symbol: str, now: datetime) -> float:
        frame = self.portfolio.daily_frame(symbol, now)
        return 0.0 if frame is None else latest_turnover_usd(frame)

    def _price(self, found: Break) -> float:
        price = self.portfolio.last_price(found.symbol)
        return price if isfinite(price) and price > 0 else found.close

    def _stand_down(self, day: date, error: Exception) -> None:
        self._past_failed_at = day
        detail = f"{type(error).__name__}: {error}"
        self.portfolio.record(
            self,
            f"scan.stood_down.{day}",
            "error",
            f"{self.family.capitalize()} scan stood down for the day: "
            f"past bars unavailable ({detail[:200]})",
        )

    def _breaks(
        self, frames: dict[str, DataFrame], session: Session, opening_end: datetime
    ) -> list[Break]:
        breaks: list[Break] = []
        for symbol, frame in frames.items():
            if frame.empty:
                continue
            opening = frame_between(frame, session.opens, opening_end)
            after = frame_since(frame, opening_end)
            if opening.empty or after.empty:
                continue
            high = float(cast(Any, opening["high"]).max())
            low = float(cast(Any, opening["low"]).min())
            if not all(isfinite(value) for value in (high, low)):
                continue
            signal = self._signal(after, high, low)
            if signal is None:
                continue
            position, direction, close = signal
            self._scanned.add(symbol)
            if not is_setup_ready(high, low, close):
                continue
            if len(after) - position > settings.breakout.signal_candles_max:
                continue
            breaks.append(
                Break(symbol, direction, high, low, close, cast(Timestamp, after.index[position]))
            )
        return breaks

    def _signal(
        self, candles: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
        for position, value in enumerate(candles["close"].tolist()):
            close = float(value)
            if not isfinite(close):
                continue
            if close > high:
                return position, 1, close
            if close < low:
                return position, -1, close
        return None
