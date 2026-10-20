"""A deterministic mock LLM adapter. No keys, network, tools or hidden labels."""
from typing import Protocol

from .models import BugContext, Strategy, digest, validate_controls


class Planner(Protocol):
    def propose(self, context: BugContext, history: tuple[dict, ...] = ()) -> list[Strategy]: ...


def base_controls() -> dict[str, int]:
    return {"concurrency": 1, "jitter_ms": 0, "clock_skew_s": 0, "cache_age_s": 0}


class MockPlanner:
    """Template-based exploration; 'LLM' denotes the seam, not a model claim."""
    name = "deterministic-mock-v1"

    def propose(self, context: BugContext, history: tuple[dict, ...] = ()) -> list[Strategy]:
        if context.gaps:
            return []
        plans = []
        for hypothesis in context.hypotheses:
            previous = [h for h in history if h["strategy"]["mechanism"] == hypothesis.mechanism]
            if any(h["feedback"]["outcome"] == "reproduced" for h in previous):
                continue
            round_index = len(previous)
            if round_index >= 3:
                continue
            controls = base_controls()
            if hypothesis.mechanism == "race":
                controls.update(concurrency=(4, 12, 24)[round_index], jitter_ms=(10, 40, 80)[round_index])
            elif hypothesis.mechanism == "expiry":
                controls["clock_skew_s"] = (30, 75, 110)[round_index]
            elif hypothesis.mechanism == "cache":
                controls["cache_age_s"] = (30, 100, 160)[round_index]
            else:
                continue
            validate_controls(controls)
            # Evidence coverage / estimated per-trial cost, with exploration penalty.
            cost = 1 + (controls["concurrency"] - 1) // 4
            score = round(len(hypothesis.evidence_ids) / cost - 0.15 * round_index, 4)
            plans.append(Strategy(
                f"S-{hypothesis.mechanism}-{round_index+1}", hypothesis.mechanism,
                hypothesis.id, hypothesis.evidence_ids, controls, score, cost,
                f"{len(hypothesis.evidence_ids)} evidence references; {round_index} prior negative runs; "
                "bounded escalation preserves other controls",
                "The simulator returns the case's matching failure signature"))
        return sorted(plans, key=lambda p: (-p.score, p.id))


def validate_strategy(strategy: dict, context: BugContext) -> None:
    validate_controls(strategy["controls"])
    hypotheses = {h.id: h for h in context.hypotheses}
    hypothesis = hypotheses.get(strategy["hypothesis_id"])
    if hypothesis is None or hypothesis.mechanism != strategy["mechanism"]:
        raise ValueError("Strategy must bind to a supported hypothesis")
    if not strategy["evidence_ids"] or not set(strategy["evidence_ids"]) <= set(hypothesis.evidence_ids):
        raise ValueError("Strategy has unsupported evidence references")


def proposal_fingerprint(proposal: dict) -> str:
    return digest(proposal)
