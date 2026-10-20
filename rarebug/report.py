"""Render a reviewable experiment report without embedding executable markup."""
from pathlib import Path

from .models import digest
from .storage import read_events


def safe(value) -> str:
    # Evidence may contain prompt injection, Markdown or HTML. Render it as plain text.
    text = str(value).replace("\n", " ").replace("\r", " ")
    for char, replacement in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                              ("|", "&#124;"), ("`", "&#96;"), ("[", "&#91;"), ("*", "&#42;")):
        text = text.replace(char, replacement)
    return text


def render_run(path: Path) -> str:
    events = read_events(path)
    proposal = events[0]["payload"]
    context = proposal["context"]
    lines = [f"# Experiment: {safe(context['case_id'])}", "", f"Round: {proposal['round']}/{proposal['max_rounds']}",
             f"Proposal digest: `{digest(proposal)}`", "", "## Static environment", ""]
    lines += [f"- {safe(k)}: {safe(v)}" for k, v in context["environment"].items()]
    lines += ["", "## Timeline (UTC)", "", "| Time | Source | Type |", "|---|---|---|"]
    lines += [f"| {safe(t['timestamp'])} | {safe(t['source_id'])} | {safe(t['kind'])} |" for t in context["timeline"]]
    lines += ["", "## Facts", "", "| Claim | Provenance | Evidence |", "|---|---|---|"]
    lines += [f"| {safe(f['statement'])} | {safe(f['provenance'])} | {safe(', '.join(f['evidence_ids']))} |"
              for f in context["facts"]]
    lines += ["", "## Hypotheses (unverified)", ""]
    lines += [f"- {safe(h['id'])}: {safe(h['statement'])}; evidence {safe(', '.join(h['evidence_ids']))}"
              for h in context["hypotheses"]]
    lines += ["", "## Exact evidence spans", "", "| ID | Source | Span | Literal quote |", "|---|---|---|---|"]
    lines += [f"| {safe(e['id'])} | {safe(e['source_id'])} | {e['start']}:{e['end']} | {safe(e['quote'])} |"
              for e in context["evidence"]]
    lines += ["", "## Strategy review", ""]
    for candidate in proposal["candidates"]:
        lines += [f"- {safe(candidate['id'])}: score={candidate['score']}, cost/trial={candidate['estimated_cost']}; "
                  f"controls={safe(candidate['controls'])}; {safe(candidate['rationale'])}"]
    if context["gaps"]:
        lines += [f"- BLOCKED: {safe(gap)}" for gap in context["gaps"]]
    if proposal["selected"]:
        lines += ["", f"Selected: {safe(proposal['selected']['id'])}",
                  f"Expected observation: {safe(proposal['selected']['expected_observation'])}",
                  f"Stop: {safe(proposal['selected']['stop_condition'])}",
                  f"Budget: {proposal['trials']} trials; seed={proposal['seed']}"]
    lines += ["", "## Decision and feedback", ""]
    if len(events) >= 2:
        decision = events[1]["payload"]
        lines += [f"{safe(decision['decision'])} by {safe(decision['actor'])}: {safe(decision['reason'])}"]
    else:
        lines += ["No decision recorded. Execution is blocked."]
    if len(events) == 3:
        result = events[2]["payload"]
        lines += ["", safe(result["feedback"]), f"Cost units: {result['cost_units']}",
                  "", "A matching synthetic signature supports this experiment, not a confirmed root cause."]
    lines += ["", "## Reproducibility", "", f"Code: `{proposal['code_digest']}`",
              f"Simulator: `{proposal['simulator_digest']}`", f"Python: `{proposal['python_version']}`",
              "", "Event hashes detect accidental changes; they are not authenticated signatures."]
    return "\n".join(lines) + "\n"
