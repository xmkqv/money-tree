import logging
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
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._export, name="state-exporter", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def record(
        self,
        status: RunStatus,
        kind: str,
        level: EventLevel,
        message: str,
        *,
        strategy_key: StrategyKey | None = None,
    ) -> None:
        with self._lock:
            if self._stopping.is_set():
                return
            self._merge(status, _event(kind, level, message, strategy_key=strategy_key))

    def close(self, status: Literal["stopped", "failed"], message: str) -> None:
        with self._lock:
            if self._stopping.is_set():
                return
            level: EventLevel = "info" if status == "stopped" else "error"
            self._merge(status, _event(f"run.{status}", level, message))
            self._stopping.set()
        self._thread.join(timeout=bot_settings.export.close_timeout_seconds)

    def _merge(self, status: RunStatus, event: StateEvent) -> None:
        if self._state.status in {"stopped", "failed"} and status != "failed":
            return
        self._state = _build_state(self._state, event.occurred_at, status=status, event=event)

    def _heartbeat(self) -> State:
        with self._lock:
            self._state = _build_state(self._state, datetime.now(UTC))
            return self._state

    def _export(self) -> None:
        with Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            str(settings.redis.url)
        ) as client:
            while True:
                is_stopped = self._stopping.wait(bot_settings.export.interval_seconds)
                self._publish(client, self._heartbeat())
                if is_stopped:
                    return

    def _publish(self, client: Redis, state: State) -> None:
        try:
            publish_state(client, state)
        except RedisError as error:
            logger.warning("State export failed: %s", type(error).__name__)


def _event(
    kind: str,
    level: EventLevel,
    message: str,
    *,
    strategy_key: StrategyKey | None = None,
) -> StateEvent:
    return StateEvent(
        kind=kind,
        occurred_at=datetime.now(UTC),
        level=level,
        message=message,
        strategy_key=strategy_key,
    )


def _build_state(
    previous: State,
    heartbeat_at: datetime,
    *,
    event: StateEvent | None = None,
    status: RunStatus | None = None,
) -> State:
    events = [*previous.events, event] if event is not None else previous.events
    return previous.model_copy(
        update={
            "status": previous.status if status is None else status,
            "heartbeat_at": heartbeat_at,
            "events": events[-bot_settings.export.events_max :],
        }
    )
