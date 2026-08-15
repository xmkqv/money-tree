from __future__ import annotations

import polars as pl

from money_tree.bars import normalize_price_bars

N_BAR_SMA_ENTRY = 20
N_BAR_SMA_TREND = 50
N_BAR_SMA_TREND_LONG = 200
N_BAR_RSI = 14
N_BAR_ADX = 14
N_BAR_ATR = 14
INDICATOR_COLUMNS = ("sma_20", "sma_50", "sma_200", "rsi_14", "atr_14", "adx_14")


def wilder_average(values: pl.Expr, period: int) -> pl.Expr:
    if period <= 0:
        raise ValueError("period must be positive")
    values = values.fill_nan(None)
    valid = values.is_not_null()
    valid_count = valid.cast(pl.UInt32).cum_sum()
    seeded = (
        pl.when(~valid)
        .then(None)
        .when(valid_count < period)
        .then(None)
        .when(valid_count == period)
        .then(values.cum_sum() / valid_count)
        .otherwise(values)
    )
    average = seeded.ewm_mean(alpha=1 / period, adjust=False, ignore_nulls=True)
    return pl.when(valid).then(average).otherwise(None)


def swing_low_expression(span: int) -> pl.Expr:
    if span <= 0:
        raise ValueError("swing span must be positive")
    low = pl.col("low")
    return pl.all_horizontal(
        low < low.shift(offset) for offset in range(-span, span + 1) if offset != 0
    )


def lazy_indicators(frame: pl.DataFrame) -> pl.LazyFrame:
    values = normalize_price_bars(frame).lazy()
    close = pl.col("close")
    high = pl.col("high")
    low = pl.col("low")
    change = close.diff()
    previous_close = close.shift(1)
    upward_move = high.diff()
    downward_move = -low.diff()
    true_range = pl.max_horizontal(
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs(),
    )
    positive_directional_move = (
        pl.when((upward_move > downward_move) & (upward_move > 0)).then(upward_move).otherwise(0.0)
    )
    negative_directional_move = (
        pl.when((downward_move > upward_move) & (downward_move > 0))
        .then(downward_move)
        .otherwise(0.0)
    )
    values = values.with_columns(
        sma_20=close.rolling_mean(N_BAR_SMA_ENTRY),
        sma_50=close.rolling_mean(N_BAR_SMA_TREND),
        sma_200=close.rolling_mean(N_BAR_SMA_TREND_LONG),
        average_gain=wilder_average(change.clip(lower_bound=0), N_BAR_RSI),
        average_loss=wilder_average((-change).clip(lower_bound=0), N_BAR_RSI),
        atr_14=wilder_average(true_range, N_BAR_ATR),
        average_positive_directional_move=wilder_average(
            positive_directional_move,
            N_BAR_ADX,
        ),
        average_negative_directional_move=wilder_average(
            negative_directional_move,
            N_BAR_ADX,
        ),
    )
    relative_strength = pl.col("average_gain") / pl.col("average_loss")
    relative_strength_index = 100 - 100 / (1 + relative_strength)
    positive_directional_index = (
        100 * pl.col("average_positive_directional_move") / pl.col("atr_14")
    )
    negative_directional_index = (
        100 * pl.col("average_negative_directional_move") / pl.col("atr_14")
    )
    directional_sum = positive_directional_index + negative_directional_index
    directional_index = (
        pl.when(directional_sum == 0)
        .then(0.0)
        .otherwise(
            100 * (positive_directional_index - negative_directional_index).abs() / directional_sum
        )
    )
    output_columns = [name for name in frame.columns if name not in INDICATOR_COLUMNS]
    return (
        values.with_columns(
            rsi_14=(
                pl.when((pl.col("average_loss") == 0) & (pl.col("average_gain") > 0))
                .then(100.0)
                .when((pl.col("average_loss") == 0) & (pl.col("average_gain") == 0))
                .then(50.0)
                .otherwise(relative_strength_index)
            ),
            directional_index=directional_index,
        )
        .with_columns(adx_14=wilder_average(pl.col("directional_index"), N_BAR_ADX))
        .select(*output_columns, *INDICATOR_COLUMNS)
    )


def calculate_indicators(frame: pl.DataFrame) -> pl.DataFrame:
    return lazy_indicators(frame).collect()
