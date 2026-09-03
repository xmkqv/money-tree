from typing import Any, cast

from pandas import DataFrame, Series

from bot.strategies.daily import DailyStrategy
from bot.strategies.shared import average_dollar_volume, tfb_entry


# Fraction of equity at risk per trade, and how many positions may run at once.
# The register states both, so they govern instead of the configured per-trade
# limit and inside the portfolio-wide position cap.
TFB_RISK_CEILING = 0.005
TFB_POSITIONS_MAX = 5

# This engine's own market screen. The cap floor is enforced by the universe
# discovery in portfolio.py, which screens on the same figure; a test pins this
# constant to UNIVERSE_CAP_MIN so the two cannot drift apart. The price and
# turnover floors are read here instead, from this engine's own daily bars: the
# shared screen reads a three-month average share count against the current
# price, and a 20-session average of the value actually traded is the closer
# measure of what a position has to get in and out of.
TFB_CAP_MIN = 500_000_000.0
TFB_PRICE_MIN = 5.0
TFB_TURNOVER_MIN = 20_000_000.0
TFB_TURNOVER_SESSIONS = 20


def tfb_market_ready(frame: DataFrame) -> bool:
    """Whether a symbol passes this engine's price and turnover floors."""
    closes = cast(Series, frame["close"])
    if closes.empty:
        return False
    price = float(cast(Any, closes).iloc[-1])
    if price < TFB_PRICE_MIN:
        return False
    return average_dollar_volume(frame, TFB_TURNOVER_SESSIONS) >= TFB_TURNOVER_MIN


class Strategy(DailyStrategy):
    stop_multiple = 2.0
    blocks_entries_before_earnings = False
    exits_before_earnings = False
    exit_needs_both = False
    caps_risk_per_trade = True
    risk_fraction_max = TFB_RISK_CEILING
    positions_max = TFB_POSITIONS_MAX

    def _entry_ready(self, frame: DataFrame) -> bool:
        return tfb_market_ready(frame) and tfb_entry(frame)
