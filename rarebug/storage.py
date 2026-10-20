"""Append-only JSON events with hash chaining and fail-closed state transitions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .models import canonical, digest


@contextmanager
def run_lock(path: Path):
    lock = path / ".lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError("Run is locked; inspect any interrupted writer before removing .lock") from exc
    try:
        yield
    finally:
        lock.rmdir()


def read_events(path: Path) -> list[dict]:
    files = sorted(path.glob("*.json"))
    if not files:
        raise ValueError("Run contains no events")
    events, previous = [], None
    for index, file in enumerate(files):
        if file.name != f"{index:04d}.json":
            raise ValueError("Event sequence has gaps or unexpected files")
        event = json.loads(file.read_text(encoding="utf-8"))
        expected = {k: v for k, v in event.items() if k != "event_hash"}
        if event.get("event_hash") != digest(expected) or event.get("previous_hash") != previous:
            raise ValueError("Snapshot hash chain verification failed")
        if event.get("sequence") != index or event.get("schema_version") != 1:
            raise ValueError("Unsupported snapshot format")
        allowed = {0: {"proposal"}, 1: {"decision"}, 2: {"execution"}}
        if event.get("type") not in allowed.get(index, set()):
            raise ValueError("Invalid event state transition")
        if index >= 1:
            fingerprint = digest(events[0]["payload"])
            if event["payload"].get("proposal_digest") != fingerprint:
                raise ValueError("Event is bound to a different proposal")
        if index == 2 and events[1]["payload"].get("decision") != "approve":
            raise ValueError("Execution requires an approved decision")
        previous = event["event_hash"]
        events.append(event)
    return events


def append_event(path: Path, kind: str, payload: dict) -> dict:
    """Caller holds run_lock; hard-link publishes a complete file without overwrite."""
    events = read_events(path) if list(path.glob("*.json")) else []
    sequence = len(events)
    allowed = {0: "proposal", 1: "decision", 2: "execution"}
    if allowed.get(sequence) != kind:
        raise ValueError("Invalid event state transition")
    if sequence and payload.get("proposal_digest") != digest(events[0]["payload"]):
        raise ValueError("Stale proposal approval/result")
    if sequence == 2 and events[1]["payload"].get("decision") != "approve":
        raise ValueError("Rejected runs cannot execute")
    event = {"schema_version": 1, "sequence": sequence, "type": kind,
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "previous_hash": events[-1]["event_hash"] if events else None, "payload": payload}
    event["event_hash"] = digest(event)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(canonical(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path / f"{sequence:04d}.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return event
