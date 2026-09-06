from mt.config.settings import settings

from .breakout import Breakout


class Breakout5m(Breakout):
    key = "breakout_5m"
    code = "o"
    variation = "5m"
    is_paused = settings.breakout_5m.is_paused
    opening_minutes = settings.breakout_5m.opening_minutes
    volume_multiple = settings.breakout_5m.volume_multiple
    target_multiples = settings.breakout_5m.target_multiples
    entry_extension_max = settings.breakout_5m.entry_extension_max
    risk_fraction_max = settings.breakout_5m.risk_fraction_max
