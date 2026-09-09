from pandas import DataFrame

from mt.config.settings import settings
from mt.indicators import average_turnover_usd, finite_row, finite_value

from .daily import Daily


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    is_paused = settings.daily_tfb.is_paused
    positions_max = settings.daily_tfb.positions_max
    equity_risk_fraction_max = settings.daily_tfb.equity_risk_fraction_max
    stop_atr_multiple = settings.daily_tfb.stop_atr_multiple
    does_heed_earnings = settings.daily_tfb.does_heed_earnings
    trend_sessions = settings.daily_tfb.trend_sessions

    @classmethod
    def does_clear(cls, frame: DataFrame) -> bool:
        sessions = settings.daily_tfb.turnover_sessions
        return average_turnover_usd(frame, sessions) >= settings.screen.turnover_usd_min

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        daily_tfb = settings.daily_tfb
        average_trend = frame[f"SMA_{cls.trend_sessions}"]
        span = daily_tfb.trend_lag_sessions + 1
        row = finite_row(
            [
                finite_value(frame["close"]),
                finite_value(average_trend),
                finite_value(average_trend, -span),
                finite_value(frame[f"ADX_{settings.indicators.period}"]),
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
