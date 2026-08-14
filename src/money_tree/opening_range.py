from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

import polars as pl

from money_tree.bars import MARKET_TIMEZONE, market_datetime_expression, normalize_price_bars
from money_tree.model import Direction

SESSION_OPEN = time(9, 30)
OPENING_RANGE_END = time(9, 35)
ENTRY_END = time(15, 55)
N_BAR_OPENING_RANGE = 5


@dataclass(frozen=True, slots=True)
class OpeningRange:
    high_price: float
    low_price: float

    def __post_init__(self) -> None:
        if self.high_price <= self.low_price:
            raise ValueError("opening range high price must exceed its low price")


@dataclass(frozen=True, slots=True)
class Breakout:
    closed_at: datetime
    close_price: float
    direction: Direction
    protective_stop_price: float


def to_market_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        moment = datetime.fromisoformat(value)
    else:
        raise TypeError(f"unsupported timestamp {value!r}")
    if moment.tzinfo is None:
        return moment.replace(tzinfo=MARKET_TIMEZONE)
    return moment.astimezone(MARKET_TIMEZONE)


def find_breakout(
    frame: pl.DataFrame,
    session_date: date,
    observed_at: datetime,
) -> Breakout | None:
    observed_at = to_market_datetime(observed_at)
    frame = normalize_price_bars(frame)
    closed_at = market_datetime_expression(frame)
    market_time = pl.col("closed_at").dt.time()
    in_opening_range = market_time < OPENING_RANGE_END
    summary = (
        frame.lazy()
        .select(
            closed_at.alias("closed_at"),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
        )
        .filter(
            (pl.col("closed_at").dt.date() == session_date)
            & (pl.col("closed_at") < observed_at)
            & market_time.is_between(SESSION_OPEN, ENTRY_END, closed="left")
        )
        .with_columns(
            opening_range_count=pl.col("closed_at").filter(in_opening_range).len(),
            opening_range_high=pl.col("high").filter(in_opening_range).max(),
            opening_range_low=pl.col("low").filter(in_opening_range).min(),
            latest_closed_at=pl.col("closed_at").max(),
        )
        .with_columns(
            breakout=(~in_opening_range)
            & (
                (pl.col("close") > pl.col("opening_range_high"))
                | (pl.col("close") < pl.col("opening_range_low"))
            )
        )
        .with_columns(breakout_count=pl.col("breakout").sum())
        .filter(pl.col("closed_at") == pl.col("latest_closed_at"))
        .select(
            "closed_at",
            "close",
            "opening_range_count",
            "opening_range_high",
            "opening_range_low",
            first=pl.col("breakout") & (pl.col("breakout_count") == 1),
            direction=(
                pl.when(pl.col("close") > pl.col("opening_range_high"))
                .then(pl.lit(Direction.LONG.value))
                .otherwise(pl.lit(Direction.SHORT.value))
            ),
        )
        .collect()
    )
    if summary.is_empty():
        return None
    candidate = summary.row(0, named=True)
    if candidate["opening_range_count"] < N_BAR_OPENING_RANGE:
        return None
    opening_range = OpeningRange(
        high_price=float(candidate["opening_range_high"]),
        low_price=float(candidate["opening_range_low"]),
    )
    if not candidate["first"]:
        return None
    direction = Direction(candidate["direction"])
    protective_stop_price = (
        opening_range.low_price if direction is Direction.LONG else opening_range.high_price
    )
    return Breakout(
        closed_at=to_market_datetime(candidate["closed_at"]),
        close_price=float(candidate["close"]),
        direction=direction,
        protective_stop_price=protective_stop_price,
    )


def should_flatten(moment: datetime) -> bool:
    return to_market_datetime(moment).time() >= ENTRY_END
