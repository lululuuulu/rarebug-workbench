import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rarebug.context import build_context, load_json
from rarebug.evaluation import evaluate
from rarebug.models import digest
from rarebug.planner import MockPlanner
from rarebug.simulator import execute_simulation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class EvaluationTests(unittest.TestCase):
    def test_seeded_simulation_is_deterministic_and_bounded(self):
        spec = load_json(DATA / "simulator/race.json")
        controls = dict(concurrency=12, jitter_ms=40, clock_skew_s=0, cache_age_s=0)
        first = execute_simulation(spec, controls, 8, 20)
        self.assertEqual(first, execute_simulation(spec, controls, 8, 20))
        self.assertEqual(first.outcome, "reproduced")
        self.assertLessEqual(first.attempts, 20)
        for trials in (0, 101, True):
            with self.subTest(trials=trials), self.assertRaises(ValueError):
                execute_simulation(spec, controls, 8, trials)

    def test_planner_has_no_simulator_or_gold_input(self):
        case = load_json(DATA / "cases/race.json")
        context = build_context(case)
        before = digest([p.to_dict() for p in MockPlanner().propose(context)])
        spec = load_json(DATA / "simulator/race.json")
        spec["mechanism"] = "cache"
        spec["signature"] = "a-secret-label"
        after = digest([p.to_dict() for p in MockPlanner().propose(context)])
        self.assertEqual(before, after)
        self.assertNotIn("a-secret-label", str(context.to_dict()))

    def test_evaluation_reproducibility_denominators_and_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            first = evaluate(DATA, Path(directory) / "a", repeats=5)
            second = evaluate(DATA, Path(directory) / "b", repeats=5)
        self.assertEqual(digest(first), digest(second))
        self.assertEqual(len(first["records"]), 9 * 3 * 5)
        self.assertTrue(all(c["expected_block"] == c["blocked"] for c in first["checks"]))
        self.assertTrue(all(r["attempts"] <= 60 for r in first["records"]))
        self.assertTrue(all(r["attempts"] == 0 for r in first["records"] if r["expected_block"]))
        rows = {(r["split"], r["policy"]): r for r in first["summary"]}
        self.assertEqual(rows["dev", "agent"]["runs"], 15)
        self.assertGreater(rows["dev", "agent"]["success_rate"], rows["dev", "no_feedback"]["success_rate"])

    def test_cli_scripted_demo_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "rarebug", "demo", "--scripted-approvals", "--out", directory],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("scripted demo", result.stdout)
            self.assertIn("reproduced", (Path(directory) / "demo.md").read_text())
            events = sorted(Path(directory).glob("*/0000.json"))
            self.assertEqual(len(events), 2)
            failed = subprocess.run([sys.executable, "-m", "rarebug", "execute", "--run", str(Path(directory) / "missing")],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 2)
            self.assertNotIn("Traceback", failed.stderr)

    def test_cli_demo_requires_explicit_scripted_approval_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "rarebug", "demo", "--out", directory],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Pending human review", result.stdout)
            self.assertEqual(len(list(Path(directory).glob("*/*.json"))), 1)
