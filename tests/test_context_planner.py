from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest

from rarebug.context import build_context, load_json, validate_bindings
from rarebug.models import digest, validate_controls
from rarebug.planner import MockPlanner, validate_strategy

DATA = Path(__file__).resolve().parents[1] / "data"


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.case = load_json(DATA / "cases/race.json")

    def test_all_fixtures_have_exact_source_bindings_and_utc_timeline(self):
        for path in (DATA / "cases").glob("*.json"):
            with self.subTest(path=path.name):
                case = load_json(path)
                context = build_context(case)
                validate_bindings(context, case)
                times = [row["timestamp"] for row in context.timeline]
                self.assertEqual(times, sorted(times))
                self.assertTrue(all(t.endswith("+00:00") for t in times))
                self.assertTrue(all(h.status == "unverified" for h in context.hypotheses))

    def test_chat_reports_are_not_observed_facts(self):
        self.case["sources"][1]["body"] = "token_expired=true"
        context = build_context(self.case)
        report = next(f for f in context.facts if f.signal == "expiry")
        self.assertEqual(report.provenance, "reported")
        self.assertEqual(next(f for f in context.facts if f.signal == "overlap").provenance, "observed")

    def test_false_quote_and_invalid_span_are_rejected(self):
        context = build_context(self.case)
        for changed in (replace(context.evidence[0], quote="invented"), replace(context.evidence[0], start=-1)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_bindings(replace(context, evidence=(changed,) + context.evidence[1:]), self.case)

    def test_duplicate_source_id_rejected(self):
        self.case["sources"].append(deepcopy(self.case["sources"][0]))
        with self.assertRaises(ValueError):
            build_context(self.case)

    def test_explicit_synthetic_opt_in_required(self):
        self.case["synthetic"] = False
        with self.assertRaises(ValueError):
            build_context(self.case)

    def test_timezone_required(self):
        self.case["sources"][0]["timestamp"] = "2026-01-15T10:00:00"
        with self.assertRaises(ValueError):
            build_context(self.case)

    def test_offsets_normalized_before_sorting(self):
        self.case["sources"][0]["timestamp"] = "2026-01-15T10:00:00+08:00"
        self.assertEqual(build_context(self.case).timeline[0]["timestamp"], "2026-01-15T02:00:00+00:00")

    def test_missing_or_conflicting_environment_blocks_plans(self):
        for name in ("missing_environment", "conflicting_environment"):
            with self.subTest(name=name):
                context = build_context(load_json(DATA / f"cases/{name}.json"))
                self.assertTrue(context.gaps)
                self.assertEqual(MockPlanner().propose(context), [])

    def test_no_signal_requests_clarification(self):
        for source in self.case["sources"]:
            if source["kind"] != "environment":
                source["body"] = "A vague complaint"
        self.assertIn("No supported mechanism", " ".join(build_context(self.case).gaps))

    def test_partial_tokens_are_not_telemetry(self):
        for source in self.case["sources"]:
            if source["kind"] != "environment":
                source["body"] = "inactive_requests=9 token_expired=trueish cache_age_s=94.5"
        self.assertEqual(build_context(self.case).hypotheses, ())

    def test_prompt_injection_cannot_add_tools_or_approve(self):
        clean = build_context(self.case)
        injected = build_context(load_json(DATA / "cases/prompt_injection.json"))
        clean_plan = MockPlanner().propose(clean)[0].to_dict()
        injected_plan = MockPlanner().propose(injected)[0].to_dict()
        self.assertEqual(clean_plan, injected_plan)
        self.assertNotIn("curl", str(injected_plan))

    def test_strategy_must_bind_to_hypothesis_evidence(self):
        context = build_context(self.case)
        plan = MockPlanner().propose(context)[0].to_dict()
        plan["evidence_ids"] = ["E-missing"]
        with self.assertRaises(ValueError):
            validate_strategy(plan, context)

    def test_feedback_changes_next_controls(self):
        context = build_context(self.case)
        first = MockPlanner().propose(context)[0]
        history = ({"strategy": first.to_dict(), "feedback": {"outcome": "not_reproduced"}},)
        second = MockPlanner().propose(context, history)[0]
        self.assertGreater(second.controls["concurrency"], first.controls["concurrency"])
        self.assertNotEqual(digest(first.to_dict()), digest(second.to_dict()))

    def test_success_stops_that_hypothesis(self):
        context = build_context(self.case)
        first = MockPlanner().propose(context)[0]
        history = ({"strategy": first.to_dict(), "feedback": {"outcome": "reproduced"}},)
        self.assertEqual(MockPlanner().propose(context, history), [])

    def test_controls_are_bounded_and_no_unknown_commands_allowed(self):
        valid = {"concurrency": 1, "jitter_ms": 0, "clock_skew_s": 0, "cache_age_s": 0}
        for invalid in ({**valid, "command": "echo hello"}, {**valid, "concurrency": 33},
                        {**valid, "jitter_ms": True}, {**valid, "clock_skew_s": -1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_controls(invalid)
