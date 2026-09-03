from bot.types import StrategyName

from .tfb_50 import TFB_RISK_MAX


DAILY_HISTORY_SESSIONS = 20
DAILY_EARNINGS_EXIT_LEAD_MINUTES = 10
DAILY_STRATEGIES: frozenset[StrategyName] = frozenset({"sma", "tfb_50"})
DAILY_STOP_ATR_MULTIPLES: dict[StrategyName, float] = {"sma": 1.5, "tfb_50": 2.0}
DAILY_EXITS_BEFORE_EARNINGS: dict[StrategyName, bool] = {"sma": True, "tfb_50": False}
DAILY_RISK_MAX: dict[StrategyName, float | None] = {"sma": None, "tfb_50": TFB_RISK_MAX}
