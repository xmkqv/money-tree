import contextlib
import logging
import queue
import threading
from datetime import UTC, datetime
from typing import Literal

from redis import Redis
from redis.exceptions import RedisError

from mt.rules.bot import settings as bot_settings
from mt.rules.settings import RuleSettings
from mt.rules.shared import settings
from mt.rules.values import StrategyKey
from mt.state import EventLevel, RunStatus, State, StateEvent, publish_state


logger = logging.getLogger(__name__)


class StateExporter:
    def __init__(
        self,
        strategies: list[StrategyKey],
        paused: list[StrategyKey],
        rules: RuleSettings,
    ) -> None:
        self._state = State(
            status="starting",
            strategies=list(strategies),
            paused=list(paused),
            heartbeat_at=datetime.now(UTC),
            rules=rules,
            events=[],
        )
        self.pending: queue.Queue[State] = queue.Queue(maxsize=1)
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
            if self.stopping.is_set():
                return
            if self._publish(
                status,
                StateEvent(
                    kind=kind,
                    occurred_at=datetime.now(UTC),
                    level=level,
                    message=message,
                    strategy_key=strategy_key,
                ),
            ):
                self._enqueue()

    def close(self, status: Literal["stopped", "failed"], message: str) -> None:
        with self.lock:
            if self.stopping.is_set():
                return
            now = datetime.now(UTC)
            if not self._publish(
                status,
                StateEvent(
                    kind=f"run.{status}",
                    occurred_at=now,
                    level="info" if status == "stopped" else "error",
                    message=message,
                ),
            ):
                self._state = _build_state(self._state, now, bot_settings.export.events_max)
            self._enqueue()
            self.stopping.set()
        self.thread.join(timeout=bot_settings.export.close_timeout_seconds)

    def _publish(self, status: RunStatus, event: StateEvent) -> bool:
        if self._state.status in {"stopped", "failed"} and status != "failed":
            return False
        self._state = _build_state(
            self._state,
            event.occurred_at,
            bot_settings.export.events_max,
            status=status,
            event=event,
        )
        return True

    def _enqueue(self) -> None:
        with contextlib.suppress(queue.Empty):
            self.pending.get_nowait()
        self.pending.put_nowait(self._state)

    def _export(self) -> None:
        with Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            str(settings.redis.url)
        ) as client:
            while True:
                try:
                    state = self.pending.get(timeout=bot_settings.export.interval_seconds)
                except queue.Empty:
                    with self.lock:
                        if self.stopping.is_set() and self.pending.empty():
                            return
                        try:
                            state = self.pending.get_nowait()
                        except queue.Empty:
                            state = self._state = _build_state(
                                self._state, datetime.now(UTC), bot_settings.export.events_max
                            )
                self._send(client, state)
                if self.stopping.is_set() and self.pending.empty():
                    return

    def _send(self, client: Redis, state: State) -> None:
        try:
            publish_state(client, state)
        except RedisError as error:
            logger.warning("State export failed: %s", type(error).__name__)


def _build_state(
    previous: State,
    heartbeat_at: datetime,
    events_max: int,
    *,
    event: StateEvent | None = None,
    status: RunStatus | None = None,
) -> State:
    events = [*previous.events, event] if event is not None else list(previous.events)
    return State(
        status=previous.status if status is None else status,
        strategies=list(previous.strategies),
        paused=list(previous.paused),
        heartbeat_at=heartbeat_at,
        rules=previous.rules,
        events=events[-events_max:],
    )
