"""Extract literal evidence; keep observations, reports and hypotheses distinct."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .models import BugContext, Evidence, Fact, Hypothesis, digest

MAX_BYTES = 1_000_000
KINDS = {"jira", "chat", "log", "environment", "feedback"}
# These recognize public fixture telemetry, not arbitrary natural-language claims.
SIGNALS = {
    "execution": (r"outcome=(reproduced|not_reproduced)", "An execution outcome was recorded"),
    "overlap": (r"active_requests=(\d+)", "Concurrent requests were recorded"),
    "delay": (r"scheduler_delay_ms=(\d+)", "Scheduler delay was recorded"),
    "expiry": (r"token_expired=true", "An expired token was reported"),
    "clock": (r"clock_offset_s=(-?\d+)", "A clock offset was recorded"),
    "stale": (r"cache_stale=true", "A stale cache response was reported"),
    "cache_age": (r"cache_age_s=(\d+)", "Cache age was recorded"),
}
MECHANISMS = {
    "race": ({"overlap", "delay"}, "Request overlap and delay may expose a race"),
    "expiry": ({"expiry", "clock"}, "Clock skew may cross the token expiration boundary"),
    "cache": ({"stale", "cache_age"}, "Cache age may cross an invalidation boundary"),
}


def load_json(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Input exceeds the 1 MB fixture limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def build_context(case: dict) -> BugContext:
    if case.get("synthetic") is not True:
        raise ValueError("This public demo accepts only explicitly synthetic fixtures")
    if not isinstance(case.get("id"), str) or not case["id"]:
        raise ValueError("Missing case id")
    sources = case.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 100:
        raise ValueError("Expected 1..100 sources")
    evidence, facts, hypotheses, timeline, gaps = [], [], [], [], []
    environment, seen, conflicting = {}, set(), set()
    for source in sources:
        sid, kind, body = source["id"], source["kind"], source["body"]
        if not isinstance(sid, str) or sid in seen or kind not in KINDS or not isinstance(body, str):
            raise ValueError("Invalid or duplicate source")
        seen.add(sid)
        timestamp = utc_timestamp(source["timestamp"])
        timeline.append({"timestamp": timestamp, "source_id": sid, "kind": kind})
        if kind == "environment":
            values = json.loads(body)
            if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
                raise ValueError("Environment values must be strings")
            for key in ("os", "runtime", "service_version"):
                if key in values:
                    if key in environment and environment[key] != values[key]:
                        conflicting.add(key)
                    environment[key] = values[key]
            eid = f"E{len(evidence) + 1}"
            evidence.append(Evidence(eid, sid, body, 0, len(body)))
            facts.append(Fact(f"F{len(facts)+1}", "environment", "Recorded environment: " + body,
                              "configuration", (eid,)))
        for signal, (pattern, statement) in SIGNALS.items():
            for match in re.finditer(r"(?<!\w)(?:" + pattern + r")(?![\w.])", body):
                eid = f"E{len(evidence) + 1}"
                evidence.append(Evidence(eid, sid, match.group(), match.start(), match.end()))
                facts.append(Fact(f"F{len(facts)+1}", signal, statement,
                                  "observed" if kind in {"log", "feedback"} else "reported", (eid,)))
    for key in ("os", "runtime", "service_version"):
        if key not in environment:
            gaps.append(f"Missing environment: {key}")
        if key in conflicting:
            gaps.append(f"Conflicting environment: {key}; human clarification required")
    for mechanism, (signals, statement) in MECHANISMS.items():
        refs = tuple(eid for fact in facts if fact.signal in signals for eid in fact.evidence_ids)
        if refs:
            hypotheses.append(Hypothesis(f"H-{mechanism}", mechanism, statement, refs))
    if not hypotheses:
        gaps.append("No supported mechanism: collect timestamped telemetry before execution")
    context = BugContext(case["id"], environment,
                         tuple(sorted(timeline, key=lambda x: (x["timestamp"], x["source_id"]))),
                         tuple(facts), tuple(hypotheses), tuple(evidence), tuple(gaps), digest(case))
    validate_bindings(context, case)
    return context


def validate_bindings(context: BugContext, case: dict) -> None:
    sources = {s["id"]: s["body"] for s in case["sources"]}
    ids = set()
    for item in context.evidence:
        if item.id in ids or item.source_id not in sources:
            raise ValueError("Duplicate or missing evidence source")
        if not 0 <= item.start < item.end <= len(sources[item.source_id]):
            raise ValueError("Invalid evidence span")
        if sources[item.source_id][item.start:item.end] != item.quote:
            raise ValueError("Evidence quote does not match its source span")
        ids.add(item.id)
    for claim in (*context.facts, *context.hypotheses):
        if not claim.evidence_ids or not set(claim.evidence_ids) <= ids:
            raise ValueError("Unbound claim")
