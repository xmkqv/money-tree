from pandas import DataFrame

from bot.strategies.daily import DailyStrategy
from bot.strategies.shared import momentum_entry


class Strategy(DailyStrategy):
    stop_multiple = 1.5
    blocks_entries_before_earnings = True
    exit_needs_both = False
    caps_risk_per_trade = False
    risk_fraction_max = None
    positions_max = None

    def _entry_ready(self, frame: DataFrame) -> bool:
        return momentum_entry(frame)
