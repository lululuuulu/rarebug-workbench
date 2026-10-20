"""Inspectable synthetic benchmark with equal trial budgets and isolated gold labels."""
from collections import defaultdict
from pathlib import Path
import platform

from .context import build_context, load_json, validate_bindings
from .models import canonical, digest
from .planner import MockPlanner, base_controls, validate_strategy
from .simulator import execute_simulation
from .workflow import MAX_ROUNDS, code_digest, with_feedback


def run_policy(case: dict, spec: dict, policy: str, seed: int, trials: int) -> dict:
    history, attempts, cost, first = [], 0, 0, None
    for round_index in range(MAX_ROUNDS):
        context = build_context(with_feedback(case, history))
        if context.gaps:
            return {"outcome": "blocked", "attempts": attempts, "cost_units": cost,
                    "first_mechanism": first, "history": history, "gaps": list(context.gaps)}
        if policy == "naive_retry":
            strategy = {"id": "baseline", "mechanism": "baseline", "controls": base_controls(), "estimated_cost": 1}
        else:
            candidates = MockPlanner().propose(context, () if policy == "no_feedback" else tuple(history))
            if not candidates:
                break
            strategy = candidates[0].to_dict()
            validate_strategy(strategy, context)
        first = first or strategy["mechanism"]
        feedback = execute_simulation(spec, strategy["controls"], seed + round_index, trials).to_dict()
        attempts += feedback["attempts"]
        cost += feedback["attempts"] * strategy["estimated_cost"]
        history.append({"strategy": strategy, "feedback": feedback})
        if feedback["outcome"] == "reproduced":
            return {"outcome": "reproduced", "attempts": attempts, "cost_units": cost,
                    "first_mechanism": first, "history": history}
    return {"outcome": "not_reproduced", "attempts": attempts, "cost_units": cost,
            "first_mechanism": first, "history": history}


def evaluate(data: Path, output: Path, repeats: int = 40, trials: int = 20) -> dict:
    if type(repeats) is not int or not 1 <= repeats <= 1000 or not 1 <= trials <= 100:
        raise ValueError("Expected 1..1000 repeats and 1..100 trials")
    manifest = load_json(data / "benchmark.json")
    records, checks, input_hashes = [], [], {}
    for entry in manifest["cases"]:
        case = load_json(data / "cases" / f"{entry['id']}.json")
        spec = load_json(data / "simulator" / f"{entry['id']}.json")
        context = build_context(case)
        validate_bindings(context, case)
        input_hashes[entry["id"]] = {"case": digest(case), "simulator": digest(spec)}
        checks.append({"case_id": case["id"], "evidence_spans_valid": True,
                       "expected_block": entry["expected_block"], "blocked": bool(context.gaps)})
        # Planner receives only BugContext/history; expected labels and spec go to scoring/execution.
        for policy in ("naive_retry", "no_feedback", "agent"):
            for repeat in range(repeats):
                seed = 10_000 + repeat * 100
                result = run_policy(case, spec, policy, seed, trials)
                records.append({"case_id": case["id"], "split": entry["split"], "policy": policy,
                                "seed": seed, "expected_block": entry["expected_block"], **result})
    grouped = defaultdict(list)
    for record in records:
        if not record["expected_block"]:
            grouped[(record["split"], record["policy"])].append(record)
    summary = []
    for (split, policy), rows in sorted(grouped.items()):
        successes = sum(r["outcome"] == "reproduced" for r in rows)
        summary.append({"split": split, "policy": policy, "runs": len(rows), "successes": successes,
                        "success_rate": round(successes / len(rows), 4),
                        "mean_attempts": round(sum(r["attempts"] for r in rows) / len(rows), 3),
                        "mean_cost_units": round(sum(r["cost_units"] for r in rows) / len(rows), 3)})
    per_case = []
    for entry in manifest["cases"]:
        for policy in ("naive_retry", "no_feedback", "agent"):
            rows = [r for r in records if r["case_id"] == entry["id"] and r["policy"] == policy]
            per_case.append({"case_id": entry["id"], "split": entry["split"], "policy": policy,
                             "runs": len(rows), "expected_block": entry["expected_block"],
                             "blocked": sum(r["outcome"] == "blocked" for r in rows),
                             "successes": sum(r["outcome"] == "reproduced" for r in rows)})
    report = {"schema_version": 1, "benchmark": "synthetic-v1", "approval_mode": "scripted-evaluation",
              "repeats": repeats, "trials_per_round": trials, "max_rounds": MAX_ROUNDS,
              "code_digest": code_digest(), "python_version": platform.python_version(),
              "manifest_digest": digest(manifest), "inputs": input_hashes,
              "checks": checks, "summary": summary, "per_case": per_case, "records": records,
              "limitations": ["Toy stochastic simulator, not real defect reproduction or LLM performance",
                              "Held-out fixtures are shifted examples, not independently collected data",
                              "Equal maximum trial budgets; cost budgets differ and are reported",
                              "Repeated seeds measure simulator variability, not external validity"]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation.json").write_text(canonical(report) + "\n", encoding="utf-8")
    lines = ["# Synthetic evaluation", "", "Offline mock planner; scripted evaluation approvals. No real model was called.",
             "", f"{repeats} seeds × {len(manifest['cases'])} cases × 3 policies; at most {MAX_ROUNDS * trials} attempts/run.",
             "", "| Split | Policy | Successful runs | Success rate | Mean attempts | Mean cost units |",
             "|---|---|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| {row['split']} | {row['policy']} | {row['successes']}/{row['runs']} | "
                     f"{row['success_rate']:.1%} | {row['mean_attempts']} | {row['mean_cost_units']} |")
    lines += ["", "Costs include unsuccessful runs; a unit is one baseline trial, with concurrency surcharges.",
              "", f"Evidence span checks: {sum(c['evidence_spans_valid'] for c in checks)}/{len(checks)}.",
              f"Expected blocking decisions: {sum(c['expected_block'] == c['blocked'] for c in checks)}/{len(checks)}.",
              "", "## Per-case counts", "", "| Case | Policy | Successes | Blocked | Expected block |",
              "|---|---|---:|---:|---|"]
    lines += [f"| {r['case_id']} | {r['policy']} | {r['successes']}/{r['runs']} | {r['blocked']} | {r['expected_block']} |"
              for r in per_case]
    lines += ["", "## Limits", ""] + [f"- {item}" for item in report["limitations"]]
    lines += ["", f"Code SHA-256: `{report['code_digest']}`", f"Python: `{report['python_version']}`",
              "", "Full per-seed strategies, feedback, fixture hashes and denominators: `evaluation.json`."]
    (output / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
