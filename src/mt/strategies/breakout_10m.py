from mt.config.settings import settings

from .breakout import Breakout


class Breakout10m(Breakout):
    key = "breakout_10m"
    code = "m"
    is_paused = settings.breakout_10m.is_paused
    opening_minutes = settings.breakout_10m.opening_minutes
    volume_multiple = settings.breakout_10m.volume_multiple
    target_multiples = settings.breakout_10m.target_multiples
    entry_extension_max = settings.breakout_10m.entry_extension_max
    equity_risk_fraction_max = settings.breakout_10m.equity_risk_fraction_max
