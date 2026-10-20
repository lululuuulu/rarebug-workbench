"""Small JSON-serializable contracts shared by all stages."""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Evidence:
    id: str
    source_id: str
    quote: str
    start: int
    end: int


@dataclass(frozen=True)
class Fact:
    id: str
    signal: str
    statement: str
    provenance: str  # observed / reported / configuration
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Hypothesis:
    id: str
    mechanism: str
    statement: str
    evidence_ids: tuple[str, ...]
    status: str = "unverified"


@dataclass(frozen=True)
class BugContext:
    case_id: str
    environment: dict[str, str]
    timeline: tuple[dict, ...]
    facts: tuple[Fact, ...]
    hypotheses: tuple[Hypothesis, ...]
    evidence: tuple[Evidence, ...]
    gaps: tuple[str, ...]
    source_digest: str

    def to_dict(self) -> dict:
        return asdict(self)


CONTROLS = {"concurrency": (1, 32), "jitter_ms": (0, 100),
            "clock_skew_s": (0, 120), "cache_age_s": (0, 180)}


def validate_controls(controls: dict) -> None:
    if set(controls) != set(CONTROLS):
        raise ValueError("Plan controls must match the simulator allowlist")
    for key, (low, high) in CONTROLS.items():
        value = controls[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Invalid bounded control: {key}")


@dataclass(frozen=True)
class Strategy:
    id: str
    mechanism: str
    hypothesis_id: str | None
    evidence_ids: tuple[str, ...]
    controls: dict[str, int]
    score: float
    estimated_cost: int
    rationale: str
    expected_observation: str
    stop_condition: str = "Stop after the trial budget or one matching failure signature"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Feedback:
    outcome: str
    attempts: int
    hits: int
    signature: str | None
    seed: int
    simulator_digest: str

    def to_dict(self) -> dict:
        return asdict(self)
