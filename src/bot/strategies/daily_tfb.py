from pandas import DataFrame, Series
from pandas_ta_classic.overlap.sma import sma as ta_sma

from bot.frames import last_close
from bot.indicators import (
    PERIOD,
    adx,
    average_dollar_volume,
    finite_row,
    finite_value,
    indicator_column,
)
from bot.types import POSITION_FRACTION_CAP
from bot.universe import PRICE_USD_MIN, TURNOVER_USD_MIN, UNIVERSE, millions, percent

from .daily import Daily


TREND_SESSIONS = 50
TURNOVER_SESSIONS = 20
ADX_MIN = 20.0
AVERAGE_LAG_SESSIONS = 3
RISK_MAX = 0.005
TFB_POSITIONS_MAX = 5


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    variation = "TFB"
    stop_atr_multiple = 2.0
    does_heed_earnings = False
    positions_max = TFB_POSITIONS_MAX
    risk_fraction_max = RISK_MAX
    market_rule = (
        f"{UNIVERSE} This strategy screens that list again on its own floors: share price "
        f"${PRICE_USD_MIN:.0f} or more, and turnover of {millions(TURNOVER_USD_MIN)} or more "
        f"averaged across the last {TURNOVER_SESSIONS} completed sessions. Turnover here is "
        "the value traded in each session, which is that session's close times its share "
        "volume. A symbol whose sessions cannot be read does not pass."
    )
    market_source = "portfolio.py · _eligible_symbols, strategies/daily_tfb.py · is_eligible"
    setup_rule = (
        "The closing price is above its 50-day average, that average is higher than it "
        "was 3 sessions ago, and the close beats the previous session's high."
    )
    confirmation_rule = f"ADX ({PERIOD}) at 20 or above."
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
        if last_close(frame) < PRICE_USD_MIN:
            return False
        return average_dollar_volume(frame, TURNOVER_SESSIONS) >= TURNOVER_USD_MIN

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        close = frame["close"]
        average_50 = ta_sma(close, length=TREND_SESSIONS, talib=False)
        directional = indicator_column(adx(frame), f"ADX_{PERIOD}", 1)
        if not isinstance(average_50, Series) or directional is None:
            return False
        span = AVERAGE_LAG_SESSIONS + 1
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
            and directional_now >= ADX_MIN
            and latest > previous_high
        )

    @classmethod
    def risk_rule(cls, per_trade: float) -> str:
        return (
            f"{percent(RISK_MAX)} of account equity per trade. This strategy states its "
            f"own {percent(RISK_MAX)} in the spec, so that governs instead of the "
            f"configured {percent(per_trade)}. A single position is never worth more than "
            f"{percent(POSITION_FRACTION_CAP)} of equity, and this strategy holds at most "
            f"{TFB_POSITIONS_MAX} positions at once."
        )
