from datetime import UTC, datetime, timedelta

import httpx
from alpaca.common.enums import BaseURL
from pandas import DataFrame, DatetimeIndex
from pydantic import Field

from mt.config.sections import BarsSection
from mt.config.values import Timeframe
from mt.exchange import TRADING_ZONE, trading_time
from mt.frames import normalize_ohlcv

from .asset import Asset, AssetType
from .http import Payload, get_json


class Bar(Payload):
    opened_at: str = Field(alias="t")
    open: float = Field(alias="o")
    high: float = Field(alias="h")
    low: float = Field(alias="l")
    close: float = Field(alias="c")
    volume: float = Field(alias="v", default=0.0)


class _BarsPage(Payload):
    bars: dict[str, list[Bar]] | None = None
    next_page_token: str | None = None


def bars_api_url() -> str:
    return BaseURL.DATA.value


def bar_frame(bars: list[Bar]) -> DataFrame:
    frame = (
        DataFrame(
            [bar.model_dump() for bar in bars],
            columns=["opened_at", "open", "high", "low", "close", "volume"],
        )
        .drop(columns="opened_at")
        .astype(float)
    )
    frame.index = DatetimeIndex([trading_time(bar.opened_at) for bar in bars], tz=TRADING_ZONE)
    return normalize_ohlcv(frame, {"open", "high", "low", "close", "volume"})


class BarsClientAlpaca:
    def __init__(self, client: httpx.AsyncClient, configuration: BarsSection) -> None:
        self._client = client
        self._configuration = configuration

    async def bars(
        self,
        assets: list[Asset],
        timeframe: Timeframe,
        start: datetime,
        end: datetime | None = None,
        *,
        limit: int,
        pages_max: int | None = None,
    ) -> dict[Asset, list[Bar]]:
        if limit <= 0 or (pages_max is not None and pages_max <= 0):
            raise ValueError("bar and page limits must be positive")
        groups: dict[AssetType, dict[str, Asset]] = {}
        rows: dict[Asset, list[Bar]] = {asset: [] for asset in assets}
        for asset in rows:
            if asset.asset_type not in (AssetType.STOCK, AssetType.CRYPTO, AssetType.OPTION):
                raise ValueError(f"historical bars do not support {asset.asset_type}")
            symbols = groups.setdefault(asset.asset_type, {})
            symbol = str(asset)
            if symbol in symbols and symbols[symbol] != asset:
                raise ValueError(f"ambiguous asset identity for {symbol}")
            symbols[symbol] = asset
        start = _utc(start)
        end = None if end is None else _utc(end)
        for asset_type, symbols in groups.items():
            params: dict[str, object] = {
                "timeframe": timeframe,
                "start": start.isoformat(),
                "limit": limit,
                "sort": "asc",
            }
            until = end
            batch_size = self._configuration.symbols_per_request
            match asset_type:
                case AssetType.STOCK:
                    path = "/v2/stocks/bars"
                    feed = (
                        self._configuration.daily_feed
                        if timeframe.endswith("Day")
                        else self._configuration.intraday_feed
                    )
                    params.update(feed=feed, adjustment="all")
                    if feed == "sip" and until is not None:
                        until = min(
                            until,
                            datetime.now(UTC)
                            - timedelta(minutes=self._configuration.sip_delay_minutes),
                        )
                case AssetType.CRYPTO:
                    path = "/v1beta3/crypto/us/bars"
                case AssetType.OPTION:
                    path = "/v1beta1/options/bars"
                    batch_size = min(batch_size, self._configuration.options_per_request)
                case _:
                    raise ValueError(f"historical bars do not support {asset_type}")
            if until is not None:
                if until < start:
                    continue
                params["end"] = until.isoformat()
            requested = list(symbols)
            for offset in range(0, len(requested), batch_size):
                batch = {
                    symbol: symbols[symbol] for symbol in requested[offset : offset + batch_size]
                }
                query = {**params, "symbols": ",".join(batch)}
                page_count = 0
                while True:
                    page = _BarsPage.model_validate(await get_json(self._client, path, query))
                    for symbol, bars in (page.bars or {}).items():
                        if symbol not in batch:
                            raise ValueError(f"unexpected bars for {symbol}")
                        rows[batch[symbol]].extend(bars)
                    page_count += 1
                    if not page.next_page_token:
                        break
                    if pages_max is not None and page_count >= pages_max:
                        raise httpx.HTTPError("Bars exceed the configured page limit")
                    query["page_token"] = page.next_page_token
        return rows


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
