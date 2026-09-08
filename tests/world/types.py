from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class World:
    state: dict[str, object] = field(default_factory=dict[str, object])
    facts: dict[str, Callable[[], bool]] = field(default_factory=dict[str, Callable[[], bool]])
    api: dict[str, Callable[..., None]] = field(default_factory=dict[str, Callable[..., None]])


@dataclass(frozen=True, slots=True)
class Case:
    key: str
    claim: str
    check: Callable[[World], None]
