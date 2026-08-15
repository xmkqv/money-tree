from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from money_tree.indicators import lazy_indicators, swing_low_expression
from money_tree.model import EntryDecision
from money_tree.risk import floor_price

BAR_INTERVAL = "day"
SLEEP_INTERVAL = "1D"
N_BAR_HISTORY = 260
RSI_MIN = 50.0
RSI_MAX = 70.0
ADX_MIN = 25.0
REWARD_RISK_RATIO_MIN = 2.0
ATR_MULTIPLIER = 1.5
SWING_SPAN = 2
USD_PRICE_TICK = 0.01


@dataclass(frozen=True, slots=True)
class TrailingStopConfiguration:
    atr_multiplier: float = ATR_MULTIPLIER
    usd_price_tick: float = USD_PRICE_TICK

    def __post_init__(self) -> None:
        if self.atr_multiplier <= 0 or self.usd_price_tick <= 0:
            raise ValueError("trailing stop values must be positive")


def decide_entry(
    frame: pl.DataFrame,
    *,
    swing_span: int = SWING_SPAN,
    usd_price_tick: float = USD_PRICE_TICK,
) -> EntryDecision | None:
    if usd_price_tick <= 0:
        raise ValueError("price tick must be positive")
    summary = (
        lazy_indicators(frame)
        .select(
            previous_close=pl.col("close").slice(-2, 1).first(),
            previous_sma_20=pl.col("sma_20").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_20=pl.col("sma_20").last(),
            sma_50=pl.col("sma_50").last(),
            sma_200=pl.col("sma_200").last(),
            rsi_14=pl.col("rsi_14").last(),
            adx_14=pl.col("adx_14").last(),
            swing_low=pl.col("low").filter(swing_low_expression(swing_span)).last(),
        )
        .filter(
            pl.all_horizontal(pl.all().is_not_null())
            & (pl.col("previous_close") < pl.col("previous_sma_20"))
            & (pl.col("close") > pl.col("sma_20"))
            & (pl.col("close") > pl.col("sma_50"))
            & (pl.col("sma_50") > pl.col("sma_200"))
            & pl.col("rsi_14").is_between(RSI_MIN, RSI_MAX, closed="both")
            & (pl.col("adx_14") > ADX_MIN)
        )
        .collect()
    )
    if summary.is_empty():
        return None
    current = summary.row(0, named=True)
    protective_stop_price = floor_price(
        float(current["swing_low"]) - usd_price_tick,
        usd_price_tick,
    )
    close_price = float(current["close"])
    if protective_stop_price >= close_price:
        return None
    return EntryDecision(protective_stop_price=protective_stop_price)


def has_exit_signal(indicator_bars: pl.DataFrame) -> bool:
    return bool(
        indicator_bars.lazy()
        .select(
            ((pl.col("close") < pl.col("sma_20")) & (pl.col("rsi_14") < RSI_MIN))
            .last()
            .fill_null(False)
        )
        .collect()
        .item()
    )


def calculate_trailing_stop_price(
    highest_price: float,
    average_true_range: float,
    initial_protective_stop_price: float,
    configuration: TrailingStopConfiguration = TrailingStopConfiguration(),
) -> float:
    if highest_price <= 0 or average_true_range <= 0 or initial_protective_stop_price <= 0:
        raise ValueError("prices and average true range must be positive")
    candidate = max(
        initial_protective_stop_price,
        highest_price - configuration.atr_multiplier * average_true_range,
    )
    return floor_price(candidate, configuration.usd_price_tick)
