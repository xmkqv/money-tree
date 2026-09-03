from pandas import DataFrame

from bot.strategies.daily import DailyStrategy
from bot.strategies.shared import tfb_entry


# Fraction of equity at risk per trade, and how many positions may run at once.
# The register states both, so they govern instead of the configured per-trade
# limit and inside the portfolio-wide position cap.
TFB_RISK_CEILING = 0.005
TFB_POSITIONS_MAX = 5


class Strategy(DailyStrategy):
    stop_multiple = 2.0
    blocks_entries_before_earnings = False
    exit_needs_both = False
    caps_risk_per_trade = True
    risk_fraction_max = TFB_RISK_CEILING
    positions_max = TFB_POSITIONS_MAX

    def _entry_ready(self, frame: DataFrame) -> bool:
        return tfb_entry(frame)
