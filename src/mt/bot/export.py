import contextlib
import logging
import queue
import threading
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from mt.config.settings import RuleSettings
from mt.config.shared import settings
from mt.config.values import StrategyKey
from mt.snapshot import EventLevel, RunStatus, StateEvent, StateSnapshot
from mt.state import publish_state


logger = logging.getLogger(__name__)


class StateExporter:
    def __init__(
        self,
        strategies: list[StrategyKey],
        paused: list[StrategyKey],
        configuration: RuleSettings,
    ) -> None:
        self.strategies = strategies
        self.paused = paused
        self.configuration = configuration
        self.run_id = uuid4()
        self.started_at = datetime.now(UTC)
        self.status: RunStatus = "starting"
        self.events: list[StateEvent] = []
        self.sequence = 0
        self.pending: queue.Queue[StateSnapshot] = queue.Queue(maxsize=1)
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
        strategy_key: StrategyKey | None = None,
    ) -> None:
        with self.lock:
            self.status = status
            self.sequence += 1
            self.events.append(
                StateEvent(
                    kind=kind,
                    occurred_at=datetime.now(UTC),
                    level=level,
                    message=message,
                    strategy_key=strategy_key,
                )
            )
            self.events = self.events[-settings.export.events_max :]
            with contextlib.suppress(queue.Empty):
                self.pending.get_nowait()
            self.pending.put_nowait(self._snapshot())

    def close(self, status: Literal["stopped", "failed"], message: str) -> None:
        if self.stopping.is_set():
            return
        level: EventLevel = "info" if status == "stopped" else "error"
        self.publish(status, f"run.{status}", level, message)
        self.stopping.set()
        self.thread.join(timeout=settings.export.close_timeout_seconds)

    def _snapshot(self) -> StateSnapshot:
        return StateSnapshot(
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
        with Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            str(settings.redis.url)
        ) as client:
            while True:
                try:
                    snapshot = self.pending.get(timeout=settings.export.interval_seconds)
                except queue.Empty:
                    if self.stopping.is_set():
                        return
                    with self.lock:
                        self.sequence += 1
                        snapshot = self._snapshot()
                self._send(client, snapshot)
                if self.stopping.is_set() and self.pending.empty():
                    return

    def _send(self, client: Redis, snapshot: StateSnapshot) -> None:
        try:
            publish_state(client, snapshot)
        except RedisError as error:
            logger.warning("State export failed: %s", type(error).__name__)
