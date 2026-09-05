from pandas import DataFrame

from .shared import PRICE_USD_MIN, TURNOVER_USD_MIN, average_dollar_volume, last_close


TFB_RISK_MAX = 0.005
TFB_POSITIONS_MAX = 5
TFB_TURNOVER_SESSIONS = 20


def is_tfb_market_ready(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    if last_close(frame) < PRICE_USD_MIN:
        return False
    return average_dollar_volume(frame, TFB_TURNOVER_SESSIONS) >= TURNOVER_USD_MIN
