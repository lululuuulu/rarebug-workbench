"""Application state machine. Only the simulator can execute a validated plan."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import platform

from . import __version__
from .context import build_context
from .models import canonical, digest
from .planner import MockPlanner, validate_strategy
from .simulator import execute_simulation
from .storage import append_event, read_events, run_lock

MAX_ROUNDS = 3


def code_digest() -> str:
    return digest({p.name: p.read_text(encoding="utf-8") for p in sorted(Path(__file__).parent.glob("*.py"))})


def with_feedback(case: dict, history: list[dict]) -> dict:
    augmented = deepcopy(case)
    # Synthetic timeline uses fixture time, not the user's local machine clock.
    end = max(datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) for s in case["sources"])
    for index, item in enumerate(history, 1):
        augmented["sources"].append({
            "id": f"execution-feedback-{index}", "kind": "feedback",
            "timestamp": (end + timedelta(seconds=index)).isoformat(),
            "body": f"outcome={item['feedback']['outcome']} attempts={item['feedback']['attempts']} "
                    f"controls={canonical(item['strategy']['controls'])}"})
    return augmented


def create_run(case: dict, spec: dict, root: Path, seed: int = 7, trials: int = 20,
               history: list[dict] | None = None, parent: str | None = None) -> Path:
    history = deepcopy(history or [])
    if type(seed) is not int or type(trials) is not int or not 1 <= trials <= 100:
        raise ValueError("Expected integer seed and 1..100 trials")
    if len(history) >= MAX_ROUNDS or any(h["feedback"]["outcome"] == "reproduced" for h in history):
        raise ValueError("Iteration stopped: success or maximum round budget reached")
    context = build_context(with_feedback(case, history))
    if spec.get("synthetic") is not True or case["id"] != spec.get("case_id"):
        raise ValueError("Simulator must be synthetic and match the case")
    candidates = MockPlanner().propose(context, tuple(history))
    proposal = {"case": case, "context": context.to_dict(), "history": history,
                "candidates": [p.to_dict() for p in candidates],
                "selected": candidates[0].to_dict() if candidates else None,
                "status": "pending_review" if candidates else "needs_clarification",
                "seed": seed, "trials": trials, "round": len(history) + 1, "max_rounds": MAX_ROUNDS,
                "planner": MockPlanner.name, "package_version": __version__,
                "code_digest": code_digest(), "python_version": platform.python_version(),
                "simulator_digest": digest(spec), "simulator": spec, "parent_proposal_digest": parent}
    path = root / digest(proposal)[:16]
    path.mkdir(parents=True, exist_ok=False)
    with run_lock(path):
        append_event(path, "proposal", proposal)
    return path


def decide(path: Path, decision: str, actor: str, reason: str, expected_digest: str) -> dict:
    if decision not in {"approve", "reject"} or not actor.strip() or not reason.strip():
        raise ValueError("Decision requires approve/reject, an actor and a non-empty reason")
    with run_lock(path):
        events = read_events(path)
        proposal = events[0]["payload"]
        if len(events) != 1 or proposal["status"] != "pending_review":
            raise ValueError("Only a pending proposal can be decided")
        if digest(proposal) != expected_digest:
            raise ValueError("Stale proposal digest; inspect the proposal again")
        return append_event(path, "decision", {"decision": decision, "actor": actor, "reason": reason,
                                              "proposal_digest": expected_digest})


def validated_proposal(proposal: dict) -> None:
    if proposal["code_digest"] != code_digest() or proposal["python_version"] != platform.python_version():
        raise ValueError("Code or Python version changed; use the original version or create a new proposal")
    context = build_context(with_feedback(proposal["case"], proposal["history"]))
    if digest(context.to_dict()) != digest(proposal["context"]) or context.gaps:
        raise ValueError("Context changed or has unresolved gaps")
    if digest(proposal["simulator"]) != proposal["simulator_digest"]:
        raise ValueError("Simulator hash mismatch")
    plans = [s.to_dict() for s in MockPlanner().propose(context, tuple(proposal["history"]))]
    if digest(plans) != digest(proposal["candidates"]) or not plans or digest(plans[0]) != digest(proposal["selected"]):
        raise ValueError("Strategy changed after proposal creation")
    validate_strategy(proposal["selected"], context)


def execute_run(path: Path) -> dict:
    with run_lock(path):
        events = read_events(path)
        if len(events) != 2 or events[1]["payload"]["decision"] != "approve":
            raise ValueError("Execution requires a fresh approved decision")
        proposal = events[0]["payload"]
        validated_proposal(proposal)
        feedback = execute_simulation(proposal["simulator"], proposal["selected"]["controls"],
                                      proposal["seed"], proposal["trials"])
        result = {"proposal_digest": digest(proposal), "feedback": feedback.to_dict(),
                  "cost_units": feedback.attempts * proposal["selected"]["estimated_cost"]}
        append_event(path, "execution", result)
        return result


def iterate_run(path: Path, root: Path) -> Path:
    events = read_events(path)
    if len(events) != 3:
        raise ValueError("Iteration requires a completed execution")
    proposal, result = events[0]["payload"], events[2]["payload"]
    validated_proposal(proposal)
    history = proposal["history"] + [{"strategy": proposal["selected"], "feedback": result["feedback"]}]
    return create_run(proposal["case"], proposal["simulator"], root, proposal["seed"] + 1,
                      proposal["trials"], history, digest(proposal))


def replay_run(path: Path) -> dict:
    events = read_events(path)
    if len(events) != 3:
        raise ValueError("Replay requires a completed execution")
    proposal = events[0]["payload"]
    validated_proposal(proposal)
    feedback = execute_simulation(proposal["simulator"], proposal["selected"]["controls"],
                                  proposal["seed"], proposal["trials"]).to_dict()
    expected = events[2]["payload"]
    if digest(feedback) != digest(expected["feedback"]):
        raise ValueError("Replayed feedback differs from snapshot")
    if expected["cost_units"] != feedback["attempts"] * proposal["selected"]["estimated_cost"]:
        raise ValueError("Replayed cost differs from snapshot")
    return {"verified": True, "events": len(events), "proposal_digest": digest(proposal), "feedback": feedback}
