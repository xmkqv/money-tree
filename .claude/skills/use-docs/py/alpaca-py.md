# [alpaca-py][alpaca:docs]

[0.44.0][alpaca:release] · sync `requests` clients · [trading][alpaca:trading] · [market data][alpaca:data] · [API reference][alpaca:api]

## trading client

```py
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient

# TradingClient(api_key=None, secret_key=None, oauth_token=None, paper=True,
#               raw_data=False, url_override=None)
client = TradingClient(key, secret, paper=True)  # paper=True targets the paper host
try:
    account = client.get_account()  # TradeAccount; money fields are str
    equity = float(account.equity or 0)
except APIError as error:
    error.status_code  # http status; error.code and error.message parse the JSON body
    raise
```

## async use

```py
import asyncio

# the clients are synchronous; 429 and 504 are retried 3 times, 3 s apart
account, positions = await asyncio.gather(
    asyncio.to_thread(client.get_account),
    asyncio.to_thread(client.get_all_positions),  # list[Position]; qty, prices are str
)
```

## models and enums

```py
from alpaca.trading.enums import OrderSide, OrderType, PositionSide, QueryOrderStatus

for position in positions:
    quantity = float(position.qty)
    is_short = position.side == PositionSide.SHORT  # str enums compare equal to "short"
    value = float(position.market_value or 0)  # Optional[str]

# Order: id: UUID, client_order_id: str, submitted_at: datetime, symbol | side | type: Optional
STOPS = {OrderType.STOP, OrderType.STOP_LIMIT, OrderType.TRAILING_STOP}
closing = OrderSide.SELL if quantity > 0 else OrderSide.BUY
```

## assets

```py
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.trading.requests import GetAssetsRequest

# get_all_assets(filter: GetAssetsRequest | None) -> list[Asset]
assets = client.get_all_assets(
    GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
)
tradable = {a.symbol: a for a in assets if a.tradable and a.fractionable}
one = client.get_asset("SYMBOL")  # symbol or UUID; APIError when unknown
```

## paginated orders

```py
from alpaca.common.enums import Sort
from alpaca.trading.requests import GetOrdersRequest

# get_orders(filter: GetOrdersRequest | None) -> list[Order]; one request, no auto-pagination
def closed_orders(client, after=None, page=500):
    rows, until = [], None
    while True:
        batch = client.get_orders(
            GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=page,
                direction=Sort.DESC,
                after=after,   # exclusive lower bound on submitted_at
                until=until,   # exclusive upper bound on submitted_at
            )
        )
        rows.extend(batch)
        if len(batch) < page:
            return rows
        until = batch[-1].submitted_at  # oldest row so far; walk backwards
```

## order lookup and cancel

```py
order = client.get_order_by_id(order_id)            # UUID | str
order = client.get_order_by_client_id(client_id)    # client_order_id <= 128 chars
client.cancel_order_by_id(order.id)                 # None; APIError when not cancelable
client.cancel_orders()                              # list[CancelOrderResponse]
client.close_position("SYMBOL")                     # Order; APIError when no position
```

## portfolio history

```py
from alpaca.trading.requests import GetPortfolioHistoryRequest

# get_portfolio_history(history_filter) -> PortfolioHistory
history = client.get_portfolio_history(
    GetPortfolioHistoryRequest(period="1A", timeframe="1D")  # 1D bars are session-labelled
)
points = list(zip(history.timestamp, history.equity))  # timestamp: epoch seconds, ints

intraday = client.get_portfolio_history(
    GetPortfolioHistoryRequest(
        period="1D", timeframe="5Min", intraday_reporting="market_hours", extended_hours=False
    )
)
history.base_value  # basis of profit_loss; None for new accounts
```

## unmodeled trading endpoints

```py
# RESTClient.get(path, params) joins base_url + "/v2" + path, retries and raises APIError
# TradingClient has no account-activities method; BrokerClient's targets the broker API
def fills(client, page=100):
    rows, token = [], None
    while True:
        batch = client.get(
            "/account/activities",
            {"activity_types": "FILL", "page_size": page, "direction": "desc", "page_token": token},
        )  # list[dict]: id, order_id, symbol, side, qty, price, transaction_time
        rows.extend(batch)
        if len(batch) < page:
            return rows
        token = batch[-1]["id"]  # cursor is the last activity id
```

## bars and latest trades

```py
from datetime import UTC, datetime, timedelta

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

data = StockHistoricalDataClient(key, secret)  # no paper flag; data host is shared

# TimeFrame(amount, unit): Minute 1-59, Hour 1-23, Day and Week 1, Month in {1,2,3,6,12}
request = StockBarsRequest(
    symbol_or_symbols=["AAA", "BBB"],
    timeframe=TimeFrame(5, TimeFrameUnit.Minute),
    start=datetime.now(UTC) - timedelta(days=5),
    end=datetime.now(UTC) - timedelta(minutes=15),  # SIP end must be 15 minutes old
    feed=DataFeed.IEX,
    adjustment=Adjustment.ALL,
)
bar_set = data.get_stock_bars(request)  # BarSet; pages of 10_000 are followed for you
bar_set.data["AAA"]                     # list[Bar]: timestamp, open, high, low, close, volume
frame = bar_set.df                      # MultiIndex (symbol, timestamp); empty when no bars

trades = data.get_stock_latest_trade(
    StockLatestTradeRequest(symbol_or_symbols=["AAA"], feed=DataFeed.IEX)
)  # dict[str, Trade]: price, size, timestamp
```

## bar frames

```py
if not frame.empty:  # an empty DataFrame has no "symbol" level
    for symbol, group in frame.groupby(level="symbol"):
        ohlcv = group.droplevel("symbol")[["open", "high", "low", "close", "volume"]]
        ohlcv = ohlcv.tz_convert("America/New_York").sort_index()  # index is UTC-aware
```

## refs

[alpaca:docs]: https://alpaca.markets/sdks/python/

[alpaca:release]: https://pypi.org/project/alpaca-py/0.44.0/

[alpaca:trading]: https://alpaca.markets/sdks/python/trading.html
    The maximum number of orders in response. Defaults to 50 and max is 500.

[alpaca:data]: https://alpaca.markets/sdks/python/market_data.html
    Timezone naive inputs assumed to be in UTC.

[alpaca:api]: https://docs.alpaca.markets/us/reference/getallorders-1
    The response will include only ones submitted until this timestamp (exclusive.)

[alpaca:orders]: https://alpaca.markets/sdks/python/api_reference/trading/orders.html
    Deprecated with just type field below.

[alpaca:feeds]: https://docs.alpaca.markets/us/v1.4.2/docs/market-data-faq
    OTC and SIP are available with premium data subscriptions.

[alpaca:history]: https://alpaca.markets/sdks/python/api_reference/trading/account.html
    This is effective only for timeframe less than 1D.

[alpaca:errors]: https://github.com/alpacahq/alpaca-py/blob/master/alpaca/common/exceptions.py
    error.status_code will have http status code.

[alpaca:raw]: https://github.com/alpacahq/alpaca-py/blob/master/alpaca/common/rest.py
    Whether API responses should be wrapped in data models or returned raw.
