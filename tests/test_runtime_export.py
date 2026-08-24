import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import httpx
import pytest
from itsdangerous import TimestampSigner

from bot import export
from bot.export import StateExporter
from bot.types import STATE_SIGNATURE_SALT, RuntimeSnapshot
from tests.world.index import (
    STATE_EXPORT_SECRET,
    runtime_snapshot,
    trading_configuration,
)
from ui.dashboard import RuntimeStore


def test_exporter_keeps_latest_snapshot_and_fifty_events_when_published_repeatedly() -> None:
    exporter = StateExporter(
        "https://web.test/internal/state",
        STATE_EXPORT_SECRET,
        ["No-op"],
        trading_configuration(),
    )

    for sequence in range(51):
        exporter.publish("running", "tick", "info", f"Event {sequence}")

    snapshot = exporter.pending.get_nowait()
    assert snapshot.sequence == 51
    assert len(snapshot.events) == 50
    assert snapshot.events[0].message == "Event 1"
    assert snapshot.events[-1].message == "Event 50"


def test_exporter_sends_signed_snapshot_when_endpoint_accepts_request() -> None:
    captured: list[bytes] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(request.content)
        return httpx.Response(204, request=request)

    exporter = StateExporter(
        "https://web.test/internal/state",
        STATE_EXPORT_SECRET,
        ["No-op"],
        trading_configuration(),
    )
    snapshot = runtime_snapshot()
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        exporter._send(client, snapshot)

    signer = TimestampSigner(
        STATE_EXPORT_SECRET,
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )
    body = signer.unsign(captured[0])
    assert RuntimeSnapshot.model_validate_json(body) == snapshot


def test_exporter_logs_and_continues_when_endpoint_is_unavailable() -> None:
    warning = Mock()

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    exporter = StateExporter(
        "https://web.test/internal/state",
        STATE_EXPORT_SECRET,
        ["No-op"],
        trading_configuration(),
    )
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
    ):
        monkeypatch.setattr(export.logger, "warning", warning)
        exporter._send(client, runtime_snapshot())

    warning.assert_called_once_with("State export failed: %s", "ConnectError")


def test_exporter_stops_after_final_snapshot_when_closed() -> None:
    responses: list[bytes] = []

    class Client:
        def __init__(self, timeout: float) -> None:
            assert timeout == 1.0

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *arguments: object) -> None:
            return None

        def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
            assert url == "https://web.test/internal/state"
            assert headers == {"Content-Type": "application/octet-stream"}
            responses.append(content)
            return httpx.Response(204, request=httpx.Request("POST", url))

    exporter = StateExporter(
        "https://web.test/internal/state",
        STATE_EXPORT_SECRET,
        ["No-op"],
        trading_configuration(),
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(export.httpx, "Client", Client)
        exporter.start()
        exporter.publish("running", "run", "info", "Trading run is active")
        exporter.close("stopped", "Trading run stopped")

    assert exporter.status == "stopped"
    assert exporter.thread.is_alive() is False
    assert responses


def test_runtime_store_accepts_newer_sequence_for_current_run() -> None:
    store = RuntimeStore()

    assert store.publish(runtime_snapshot(sequence=1)) is True
    assert store.publish(runtime_snapshot(sequence=2)) is True
    assert store.read() is not None
    assert store.read().sequence == 2


def test_runtime_store_rejects_replay_for_current_run() -> None:
    store = RuntimeStore()
    snapshot = runtime_snapshot(sequence=2)
    store.publish(snapshot)

    assert store.publish(runtime_snapshot(sequence=2)) is False
    assert store.publish(runtime_snapshot(sequence=1)) is False
    assert store.read() == snapshot


def test_runtime_store_rejects_older_replacement_run() -> None:
    store = RuntimeStore()
    now = datetime.now(UTC)
    current = runtime_snapshot(started_at=now)
    older = runtime_snapshot(
        run_id=UUID("646c0ba8-4d4d-4dfa-aec3-d40cb32a872d"),
        started_at=now - timedelta(minutes=1),
    )
    store.publish(current)

    assert store.publish(older) is False
    assert store.read() == current


def test_runtime_store_accepts_newer_replacement_run() -> None:
    store = RuntimeStore()
    now = datetime.now(UTC)
    store.publish(runtime_snapshot(started_at=now - timedelta(minutes=2)))
    replacement = runtime_snapshot(
        run_id=UUID("646c0ba8-4d4d-4dfa-aec3-d40cb32a872d"),
        started_at=now - timedelta(minutes=1),
    )

    assert store.publish(replacement) is True
    assert store.read() == replacement
