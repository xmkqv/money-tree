from pandas import DataFrame, Series
from pandas_ta_classic.overlap.sma import sma as ta_sma

from bot.config import settings
from bot.frames import last_close
from bot.indicators import (
    adx,
    average_dollar_volume,
    finite_row,
    finite_value,
    indicator_column,
)
from bot.universe import UNIVERSE, millions, percent

from .daily import Daily


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    variation = "TFB"
    is_paused = settings.daily_tfb.is_paused
    positions_max = settings.daily_tfb.positions_max
    risk_fraction_max = settings.daily_tfb.risk_fraction_max
    stop_atr_multiple = settings.daily_tfb.stop_atr_multiple
    does_heed_earnings = settings.daily_tfb.does_heed_earnings
    market_rule = (
        f"{UNIVERSE} This strategy screens that list again on its own floors: share price "
        f"${settings.universe.price_usd_min:.0f} or more, and turnover of "
        f"{millions(settings.universe.turnover_usd_min)} or more averaged across the last "
        f"{settings.daily_tfb.turnover_sessions} completed sessions. Turnover here is "
        "the value traded in each session, which is that session's close times its share "
        "volume. A symbol whose sessions cannot be read does not pass."
    )
    market_source = "portfolio.py · _eligible_symbols, strategies/daily_tfb.py · is_eligible"
    setup_rule = (
        f"The closing price is above its {settings.daily_tfb.trend_sessions}-day average, that "
        f"average is higher than it was {settings.daily_tfb.average_lag_sessions} sessions ago, "
        "and the close beats the previous session's high."
    )
    confirmation_rule = (
        f"ADX ({settings.indicators.period}) at {settings.daily_tfb.adx_min:g} or above."
    )
    entry_rule = (
        "Market buy at the open, then retried every iteration until the close. The "
        "setup is cut from completed sessions, so the day's list is scanned once and "
        "re-offered. A name that could not be funded at the open is taken later in the "
        "day if room frees up. It may have missed out because no slot was left, because "
        "no affordable size was available, or because another strategy held it. Upcoming "
        "earnings do not block an entry for this strategy."
    )
    setup_source = "strategies/daily_tfb.py · does_enter"
    entry_source = "strategies/daily.py · run"
    risk_source = "strategies/daily.py · run, portfolio.py · enter"

    @classmethod
    def is_eligible(cls, frame: DataFrame) -> bool:
        if frame.empty:
            return False
        if last_close(frame) < settings.universe.price_usd_min:
            return False
        sessions = settings.daily_tfb.turnover_sessions
        return average_dollar_volume(frame, sessions) >= settings.universe.turnover_usd_min

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        daily_tfb = settings.daily_tfb
        period = settings.indicators.period
        close = frame["close"]
        average_50 = ta_sma(close, length=daily_tfb.trend_sessions, talib=False)
        directional = indicator_column(adx(frame), f"ADX_{period}", 1)
        if not isinstance(average_50, Series) or directional is None:
            return False
        span = daily_tfb.average_lag_sessions + 1
        if average_50.tail(span).count() < span:
            return False
        row = finite_row(
            [
                finite_value(close),
                finite_value(average_50),
                finite_value(average_50, -span),
                finite_value(directional),
                finite_value(frame["high"], -2),
            ]
        )
        if row is None:
            return False
        latest, latest_average, lagged_average, directional_now, previous_high = row
        return (
            latest > latest_average
            and latest_average > lagged_average
            and directional_now >= daily_tfb.adx_min
            and latest > previous_high
        )

    @classmethod
    def risk_rule(cls, per_trade: float) -> str:
        own = percent(settings.daily_tfb.risk_fraction_max)
        return (
            f"{own} of account equity per trade. This strategy states its "
            f"own {own} in the spec, so that governs instead of the "
            f"configured {percent(per_trade)}. A single position is never worth more than "
            f"{percent(settings.risk.position_fraction_max)} of equity, and this strategy holds "
            f"at most {settings.daily_tfb.positions_max} positions at once."
        )
