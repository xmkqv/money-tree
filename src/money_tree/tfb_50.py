from __future__ import annotations

from datetime import date
from enum import StrEnum

import polars as pl

from money_tree.bars import market_datetime_expression, normalize_price_bars
from money_tree.indicators import lazy_indicators, swing_low_expression
from money_tree.model import EntryDecision
from money_tree.risk import floor_price

BAR_INTERVAL = "day"
SLEEP_INTERVAL = "1D"
N_BAR_HISTORY = 60
N_BAR_SMA_SLOPE = 3
ADX_MAX = 20.0
RSI_EXIT_MAX = 50.0
SWING_SPAN = 2
USD_PRICE_TICK = 0.01


class ExitSignal(StrEnum):
    PREVIOUS_LOW = "close below previous low"
    EMERGENCY = "close below 20 SMA with RSI below 50"


def _find_latest_swing_low(
    frame: pl.DataFrame,
    swing_span: int,
    usd_price_tick: float,
) -> float | None:
    value = (
        normalize_price_bars(frame)
        .lazy()
        .select(pl.col("low").filter(swing_low_expression(swing_span)).last())
        .collect()
        .item()
    )
    if value is None:
        return None
    return floor_price(float(value), usd_price_tick)


def find_highest_swing_low(
    frame: pl.DataFrame,
    entered_on: date,
    *,
    swing_span: int = SWING_SPAN,
    usd_price_tick: float = USD_PRICE_TICK,
) -> float | None:
    if usd_price_tick <= 0:
        raise ValueError("price tick must be positive")
    values = normalize_price_bars(frame).with_columns(
        market_datetime_expression(frame).alias("market_datetime")
    )
    value = (
        values.lazy()
        .filter(
            swing_low_expression(swing_span)
            & (pl.col("market_datetime").dt.date() >= entered_on)
        )
        .select(pl.col("low").max())
        .collect()
        .item()
    )
    if value is None:
        return None
    return floor_price(float(value), usd_price_tick)


def decide_entry(
    frame: pl.DataFrame,
    *,
    n_bar_sma_slope: int = N_BAR_SMA_SLOPE,
    swing_span: int = SWING_SPAN,
    usd_price_tick: float = USD_PRICE_TICK,
) -> EntryDecision | None:
    if n_bar_sma_slope <= 0 or usd_price_tick <= 0:
        raise ValueError("entry values must be positive")
    protective_stop_price = _find_latest_swing_low(frame, swing_span, usd_price_tick)
    if protective_stop_price is None:
        return None
    summary = (
        lazy_indicators(frame)
        .select(
            previous_high=pl.col("high").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_50=pl.col("sma_50").last(),
            prior_sma_50=pl.col("sma_50").slice(-(n_bar_sma_slope + 1), 1).first(),
            adx_14=pl.col("adx_14").last(),
        )
        .filter(
            pl.all_horizontal(pl.all().is_not_null())
            & (pl.col("close") > pl.col("sma_50"))
            & (pl.col("sma_50") > pl.col("prior_sma_50"))
            & (pl.col("adx_14") < ADX_MAX)
            & (pl.col("close") > pl.col("previous_high"))
        )
        .collect()
    )
    if summary.is_empty():
        return None
    close_price = float(summary.item(0, "close"))
    if protective_stop_price >= close_price:
        return None
    return EntryDecision(protective_stop_price=protective_stop_price)


def decide_exit(frame: pl.DataFrame) -> ExitSignal | None:
    summary = (
        lazy_indicators(frame)
        .select(
            previous_low=pl.col("low").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_20=pl.col("sma_20").last(),
            rsi_14=pl.col("rsi_14").last(),
        )
        .collect()
    )
    if summary.is_empty():
        return None
    current = summary.row(0, named=True)
    if (
        current["close"] is not None
        and current["previous_low"] is not None
        and current["close"] < current["previous_low"]
    ):
        return ExitSignal.PREVIOUS_LOW
    emergency_values = (current["close"], current["sma_20"], current["rsi_14"])
    if all(value is not None for value in emergency_values) and (
        current["close"] < current["sma_20"] and current["rsi_14"] < RSI_EXIT_MAX
    ):
        return ExitSignal.EMERGENCY
    return None
