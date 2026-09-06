from .breakout import Breakout


class Breakout5m(Breakout):
    key = "breakout_5m"
    code = "o"
    variation = "5m"
    opening_minutes = 5
    volume_multiple = 1.3
    target_multiples = (1.5, 2.5, 4.0)
    entry_extension_max = None
    risk_fraction_max = 0.0015
