"""Zero-dependency CLI entrypoint."""
import argparse
import json
from pathlib import Path
import sys

from .context import load_json
from .evaluation import evaluate
from .models import digest
from .report import render_run
from .storage import read_events
from .workflow import create_run, decide, execute_run, iterate_run, replay_run


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="rarebug", description="Offline synthetic rare-bug agent workbench")
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Build context and propose a bounded experiment")
    plan.add_argument("--case", type=Path, required=True)
    plan.add_argument("--simulator", type=Path, required=True)
    plan.add_argument("--out", type=Path, default=Path("runs"))
    plan.add_argument("--seed", type=int, default=7)
    plan.add_argument("--trials", type=int, default=20)
    for name in ("inspect", "decide", "execute", "iterate", "replay", "report"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--run", type=Path, required=True)
        if name == "decide":
            cmd.add_argument("--decision", choices=("approve", "reject"), required=True)
            cmd.add_argument("--actor", required=True)
            cmd.add_argument("--reason", required=True)
            cmd.add_argument("--proposal-digest", required=True)
        if name == "iterate":
            cmd.add_argument("--out", type=Path, default=Path("runs"))
        if name == "report":
            cmd.add_argument("--out", type=Path, required=True)
    demo = commands.add_parser("demo", help="Scripted demo; approvals require explicit opt-in")
    demo.add_argument("--data", type=Path, default=Path("data"))
    demo.add_argument("--out", type=Path, default=Path("runs/demo"))
    demo.add_argument("--scripted-approvals", action="store_true")
    evaluation = commands.add_parser("evaluate", help="Evaluate synthetic fixtures, never a real system")
    evaluation.add_argument("--data", type=Path, default=Path("data"))
    evaluation.add_argument("--out", type=Path, default=Path("runs/evaluation"))
    evaluation.add_argument("--repeats", type=int, default=40)
    evaluation.add_argument("--trials", type=int, default=20)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            path = create_run(load_json(args.case), load_json(args.simulator), args.out, args.seed, args.trials)
            print(path)
            print(render_run(path))
        elif args.command == "inspect":
            print(render_run(args.run))
        elif args.command == "decide":
            result = decide(args.run, args.decision, args.actor, args.reason, args.proposal_digest)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "execute":
            print(json.dumps(execute_run(args.run), ensure_ascii=False, indent=2))
        elif args.command == "iterate":
            print(iterate_run(args.run, args.out))
        elif args.command == "replay":
            print(json.dumps(replay_run(args.run), ensure_ascii=False, indent=2))
        elif args.command == "report":
            text = render_run(args.run)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(args.out)
        elif args.command == "evaluate":
            result = evaluate(args.data, args.out, args.repeats, args.trials)
            print(json.dumps({"summary": result["summary"], "out": str(args.out)}, indent=2))
            if any(c["expected_block"] != c["blocked"] for c in result["checks"]):
                return 1
        elif args.command == "demo":
            args.out.mkdir(parents=True, exist_ok=True)
            case = load_json(args.data / "cases/race.json")
            spec = load_json(args.data / "simulator/race.json")
            path = create_run(case, spec, args.out, seed=7)
            paths = []
            for _ in range(3):
                paths.append(path)
                if not args.scripted_approvals:
                    break
                proposal = read_events(path)[0]["payload"]
                decide(path, "approve", "scripted-demo-not-a-human", "Explicit CLI demo opt-in", digest(proposal))
                result = execute_run(path)
                replay_run(path)
                if result["feedback"]["outcome"] == "reproduced" or len(paths) == 3:
                    break
                path = iterate_run(path, args.out)
            report = "\n---\n\n".join(render_run(p) for p in paths)
            (args.out / "demo.md").write_text(report, encoding="utf-8")
            print(f"Report: {args.out / 'demo.md'}")
            print(f"Last run: {paths[-1]}")
            print("Approval mode: scripted demo" if args.scripted_approvals else "Pending human review")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
