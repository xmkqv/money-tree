from mt.snapshot import StateSnapshot


STATE_SIGNATURE_ENVELOPE_BYTES = 51


class StateStore:
    def __init__(self) -> None:
        self._snapshot: StateSnapshot | None = None

    def publish(self, snapshot: StateSnapshot) -> bool:
        current = self._snapshot
        if current is not None:
            if snapshot.run_id == current.run_id and snapshot.sequence <= current.sequence:
                return False
            if snapshot.run_id != current.run_id and snapshot.started_at <= current.started_at:
                return False
        self._snapshot = snapshot
        return True

    def read(self) -> StateSnapshot | None:
        return self._snapshot
