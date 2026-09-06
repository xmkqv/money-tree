from .breakout import Breakout


class Breakout10m(Breakout):
    key = "breakout_10m"
    code = "m"
    variation = "10m"
    is_paused = True
    opening_minutes = 10
    volume_multiple = 1.5
    target_multiples = (2.0, 3.0, 5.0)
    entry_extension_max = 0.25
