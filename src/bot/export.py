import contextlib
import hmac
import logging
import queue
import threading
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field


LOGGER = logging.getLogger(__name__)
EXPORT_INTERVAL_SECONDS = 5

type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)


class RuntimeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategy: str = Field(min_length=1, max_length=100)
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    events: list[RuntimeEvent] = Field(max_length=50)


class StateExporter:
    def __init__(self, url: str, secret: str, strategy: str) -> None:
        self.url = url
        self.secret = secret.encode()
        self.strategy = strategy
        self.run_id = uuid4()
        self.started_at = datetime.now(UTC)
        self.status: RunStatus = "starting"
        self.events: list[RuntimeEvent] = []
        self.sequence = 0
        self.pending: queue.Queue[RuntimeSnapshot] = queue.Queue(maxsize=1)
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(
            target=self._export,
            name="state-exporter",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()

    def publish(self, status: RunStatus, kind: str, level: EventLevel, message: str) -> None:
        with self.lock:
            self.status = status
            self.sequence += 1
            self.events.append(
                RuntimeEvent(
                    id=f"{self.run_id}:{self.sequence}",
                    kind=kind,
                    occurred_at=datetime.now(UTC),
                    level=level,
                    message=message,
                )
            )
            self.events = self.events[-50:]
            with contextlib.suppress(queue.Empty):
                self.pending.get_nowait()
            self.pending.put_nowait(self._snapshot())

    def close(self, status: Literal["stopped", "failed"], message: str) -> None:
        level: EventLevel = "info" if status == "stopped" else "error"
        self.publish(status, status, level, message)
        self.stopping.set()
        self.thread.join(timeout=3)

    def _snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            run_id=self.run_id,
            sequence=self.sequence,
            status=self.status,
            strategy=self.strategy,
            started_at=self.started_at,
            heartbeat_at=datetime.now(UTC),
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
        body = snapshot.model_dump_json().encode()
        timestamp = str(int(time.time()))
        signed = timestamp.encode() + b"." + body
        signature = hmac.digest(self.secret, signed, "sha256").hex()
        try:
            response = client.post(
                self.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-State-Timestamp": timestamp,
                    "X-State-Signature": signature,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            LOGGER.warning("State export failed: %s", type(error).__name__)
