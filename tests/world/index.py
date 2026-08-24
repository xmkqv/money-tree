import hashlib
import json
import os
from base64 import b64encode
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from pandas import DataFrame, DatetimeIndex

from bot.strategies.shared import TRADING_ZONE
from bot.types import STATE_SIGNATURE_SALT, RuntimeEvent, RuntimeSnapshot, TradingConfiguration
from ui.app import create_app
from ui.config import WebSettings


SESSION_SECRET = "session-secret-0123456789abcdef"
STATE_EXPORT_SECRET = "export-secret-0123456789abcdef"
WEB_ENVIRONMENT = {
    "ALLOWED_RAILWAY_EMAILS": "operator@example.com",
    "ALPACA_API_KEY": "alpaca-key",
    "ALPACA_API_SECRET": "alpaca-secret",
    "ALPACA_IS_PAPER": "true",
    "APP_BASE_URL": "https://testserver",
    "RAILWAY_OAUTH_CLIENT_ID": "railway-client",
    "RAILWAY_OAUTH_CLIENT_SECRET": "railway-secret",
    "RAILWAY_OAUTH_REDIRECT_URI": "https://testserver/auth/callback",
    "SESSION_SECRET": SESSION_SECRET,
    "STATE_EXPORT_SECRET": STATE_EXPORT_SECRET,
}


def trading_configuration() -> TradingConfiguration:
    return TradingConfiguration(
        fractional_orders=True,
        position_fraction_max=0.1,
        risk_per_day_max=0.02,
        risk_per_trade_max=0.005,
    )


def web_settings(**overrides: str) -> WebSettings:
    with patch.dict(os.environ, {**WEB_ENVIRONMENT, **overrides}):
        return WebSettings(_env_file=None)


def runtime_snapshot(
    *,
    sequence: int = 1,
    run_id: UUID = UUID("8f558d63-d47d-4a5f-8f77-95b0bf55a591"),
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
) -> RuntimeSnapshot:
    now = datetime.now(UTC)
    return RuntimeSnapshot(
        run_id=run_id,
        sequence=sequence,
        status="running",
        strategies=["No-op"],
        started_at=started_at or now - timedelta(minutes=1),
        heartbeat_at=heartbeat_at or now,
        configuration=trading_configuration(),
        events=[
            RuntimeEvent(
                kind="run",
                occurred_at=now,
                level="info",
                message="Trading run is active",
            )
        ],
    )


def sign_snapshot(snapshot: RuntimeSnapshot, *, expired: bool = False) -> bytes:
    signer_class = _ExpiredSigner if expired else TimestampSigner
    signer = signer_class(
        STATE_EXPORT_SECRET,
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )
    return signer.sign(snapshot.model_dump_json().encode())


def authenticate(client: TestClient, csrf_token: str = "csrf-token") -> None:
    session = b64encode(
        json.dumps({"user_sub": "operator", "csrf_token": csrf_token}).encode()
    )
    cookie = TimestampSigner(SESSION_SECRET).sign(session).decode()
    client.cookies.set("money_tree_session", cookie, secure=True)


@contextmanager
def web_client() -> Iterator[TestClient]:
    with patch.dict(os.environ, WEB_ENVIRONMENT):
        with TestClient(create_app(), base_url="https://testserver") as client:
            yield client


def market_frame(rows: int = 20) -> DataFrame:
    index = DatetimeIndex(
        [datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=offset) for offset in range(rows)]
    )
    closes = [100.0 + offset for offset in range(rows)]
    return DataFrame(
        {
            "open": [value - 0.5 for value in closes],
            "high": [value + 1.0 for value in closes],
            "low": [value - 1.0 for value in closes],
            "close": closes,
            "volume": [1_000_000.0 for _ in closes],
        },
        index=index,
    )


def relative_volume_frame(day: date, history_sessions: int = 20) -> DataFrame:
    rows: list[dict[str, float]] = []
    timestamps: list[datetime] = []
    for session_offset in range(history_sessions, 0, -1):
        session = day - timedelta(days=session_offset)
        timestamps.extend(
            [
                datetime.combine(session, time(9, 30), TRADING_ZONE),
                datetime.combine(session, time(10, 0), TRADING_ZONE),
            ]
        )
        rows.extend([{"volume": 500_000.0}, {"volume": 500_000.0}])
    timestamps.extend(
        [
            datetime.combine(day, time(9, 30), TRADING_ZONE),
            datetime.combine(day, time(10, 0), TRADING_ZONE),
        ]
    )
    rows.extend([{"volume": 700_000.0}, {"volume": 300_000.0}])
    return DataFrame(rows, index=DatetimeIndex(timestamps))


def decimal(value: str) -> Decimal:
    return Decimal(value)


class _ExpiredSigner(TimestampSigner):
    def get_timestamp(self) -> int:
        return super().get_timestamp() - 60
