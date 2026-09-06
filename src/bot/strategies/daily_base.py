from bot.types import StrategyName

from .sma20 import SMA20_NOTIONAL_USD, SMA20_POSITIONS_MAX, SMA20_STOP_FRACTION
from .tfb_50 import TFB_POSITIONS_MAX, TFB_RISK_MAX


DAILY_HISTORY_SESSIONS = 20
DAILY_EARNINGS_EXIT_LEAD_MINUTES = 10
DAILY_STRATEGIES: frozenset[StrategyName] = frozenset({"sma", "tfb_50", "sma20"})
# The strategies whose stop is cut from the daily ATR. 20SMA is not one of them:
# it opens at a fixed distance below the fill and trails on 4-hour candles.
DAILY_STOP_ATR_MULTIPLES: dict[StrategyName, float] = {"sma": 1.5, "tfb_50": 2.0}
# The stop a strategy opens with, as a fraction of the price it filled at.
DAILY_STOP_FRACTIONS: dict[StrategyName, float] = {"sma20": SMA20_STOP_FRACTION}
DAILY_EXITS_BEFORE_EARNINGS: dict[StrategyName, bool] = {
    "sma": True,
    "tfb_50": False,
    "sma20": False,
}
DAILY_RISK_MAX: dict[StrategyName, float | None] = {
    "sma": None,
    "tfb_50": TFB_RISK_MAX,
    "sma20": None,
}
# Whether the strategy waits for the wider market to be rising before it opens
# anything. 20SMA states no market condition, so it trades its own signal.
DAILY_REQUIRES_MARKET: dict[StrategyName, bool] = {
    "sma": True,
    "tfb_50": True,
    "sma20": False,
}
DAILY_POSITIONS_MAX: dict[StrategyName, int] = {
    "tfb_50": TFB_POSITIONS_MAX,
    "sma20": SMA20_POSITIONS_MAX,
}
# A position worth a fixed number of dollars rather than a share of equity.
DAILY_NOTIONAL_USD: dict[StrategyName, float] = {"sma20": SMA20_NOTIONAL_USD}
