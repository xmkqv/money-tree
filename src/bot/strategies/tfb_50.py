from pandas import DataFrame

from bot.strategies.daily import DailyStrategy
from bot.strategies.shared import tfb_entry


class Strategy(DailyStrategy):
    stop_multiple = 2.0
    blocks_entries_before_earnings = False
    caps_risk_per_trade = True
    exit_average_length = 20

    def _entry_ready(self, frame: DataFrame) -> bool:
        return tfb_entry(frame)
