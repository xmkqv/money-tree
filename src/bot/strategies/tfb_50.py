from pandas import DataFrame

from .shared import average_dollar_volume, last_close


TFB_RISK_MAX = 0.005
TFB_POSITIONS_MAX = 5
TFB_PRICE_USD_MIN = 5.0
TFB_TURNOVER_USD_MIN = 20_000_000.0
TFB_TURNOVER_SESSIONS = 20


def is_tfb_market_ready(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    price = last_close(frame)
    if price < TFB_PRICE_USD_MIN:
        return False
    return average_dollar_volume(frame, TFB_TURNOVER_SESSIONS) >= TFB_TURNOVER_USD_MIN
