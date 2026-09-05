import contextlib
import hashlib
import logging
import queue
import sys
import threading
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import httpx
from itsdangerous import TimestampSigner

from .types import (
    STATE_SIGNATURE_SALT,
    EventLevel,
    RunStatus,
    RuntimeEvent,
    RuntimeSnapshot,
    TradingConfiguration,
)


logger = logging.getLogger(__name__)
EXPORT_INTERVAL_SECONDS = 5

# Where the bot's own account of itself is written down.
#
#   _record_event ─┬─▶ publish ─▶ snapshot ─▶ dashboard   memory, both ends
#                  └─▶ log_event ─────────▶ stdout        kept by the host
#
# The snapshot is held in memory at both ends, so it starts again whenever
# either side restarts. The log is the copy that survives a restart, and it is
# the only place a warning raised on Tuesday can still be read on Thursday.
event_log = logging.getLogger("bot.events")
LOG_LEVELS: dict[EventLevel, int] = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def _configure_event_log() -> None:
    """Give the event log its own line to stdout.

    Lumibot leaves the root logger without a handler and sets it to warnings
    only, so an event handed to the root would be dropped if it was routine and
    printed bare if it was not. This logger carries its own handler and does not
    pass records upward, so every event is written the same way whatever lumibot
    does to the root. Done on first use, so importing this module changes
    nothing on its own.
    """
    if event_log.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    event_log.addHandler(handler)
    event_log.setLevel(logging.INFO)
    event_log.propagate = False


def log_event(
    kind: str,
    level: EventLevel,
    message: str,
    strategy: str | None = None,
) -> None:
    """Write one event to stdout, where the host keeps it."""
    _configure_event_log()
    named = "" if strategy is None else f"[{strategy}] "
    event_log.log(LOG_LEVELS[level], "%s %s%s", kind, named, message)


class StateExporter:
    def __init__(
        self,
        url: str,
        secret: str,
        strategies: list[str],
        paused: list[str],
        configuration: TradingConfiguration,
    ) -> None:
        self.url = url
        self.signer = TimestampSigner(
            secret,
            salt=STATE_SIGNATURE_SALT,
            digest_method=hashlib.sha256,
        )
        self.strategies = strategies
        self.paused = paused
        self.configuration = configuration
        self.run_id = uuid4()
        self.started_at = datetime.now(UTC)
        self.status: RunStatus = "starting"
        self.events: list[RuntimeEvent] = []
        self.sequence = 0
        self.pending: queue.Queue[RuntimeSnapshot] = queue.Queue(maxsize=1)
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._export, name="state-exporter", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def publish(
        self,
        status: RunStatus,
        kind: str,
        level: EventLevel,
        message: str,
        *,
        strategy: str | None = None,
    ) -> None:
        log_event(kind, level, message, strategy)
        with self.lock:
            self.status = status
            self.sequence += 1
            self.events.append(
                RuntimeEvent(
                    kind=kind,
                    occurred_at=datetime.now(UTC),
                    level=level,
                    message=message,
                    strategy=strategy,
                )
            )
            self.events = self.events[-50:]
            with contextlib.suppress(queue.Empty):
                self.pending.get_nowait()
            self.pending.put_nowait(self._snapshot())

    def close(self, status: Literal["stopped", "failed"], message: str) -> None:
        if self.stopping.is_set():
            return
        level: EventLevel = "info" if status == "stopped" else "error"
        self.publish(status, status, level, message)
        self.stopping.set()
        self.thread.join(timeout=5)

    def _snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            run_id=self.run_id,
            sequence=self.sequence,
            status=self.status,
            strategies=self.strategies,
            paused=self.paused,
            started_at=self.started_at,
            heartbeat_at=datetime.now(UTC),
            configuration=self.configuration,
            events=list(self.events),
        )

    def _export(self) -> None:
        with httpx.Client(timeout=1.0) as client:
            while True:
                try:
                    snapshot = self.pending.get(timeout=EXPORT_INTERVAL_SECONDS)
                except queue.Empty:
                    if self.stopping.is_set():
                        return
                    with self.lock:
                        self.sequence += 1
                        snapshot = self._snapshot()
                self._send(client, snapshot)
                if self.stopping.is_set() and self.pending.empty():
                    return

    def _send(self, client: httpx.Client, snapshot: RuntimeSnapshot) -> None:
        body = self.signer.sign(snapshot.model_dump_json().encode())
        try:
            response = client.post(
                self.url,
                content=body,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning("State export failed: %s", type(error).__name__)
