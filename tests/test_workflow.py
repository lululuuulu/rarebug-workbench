import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rarebug.context import load_json
from rarebug.models import digest
from rarebug.report import render_run
from rarebug.storage import read_events, run_lock
from rarebug.workflow import create_run, decide, execute_run, iterate_run, replay_run

DATA = Path(__file__).resolve().parents[1] / "data"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = load_json(DATA / "cases/race.json")
        self.spec = load_json(DATA / "simulator/race.json")
        self.run = create_run(self.case, self.spec, self.root)

    def approve(self, run=None):
        run = run or self.run
        fingerprint = digest(read_events(run)[0]["payload"])
        return decide(run, "approve", "test-reviewer", "Reviewed synthetic bounded controls", fingerprint)

    def test_execute_without_approval_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            execute_run(self.run)
        self.assertEqual(len(read_events(self.run)), 1)

    def test_stale_approval_digest_rejected_without_event(self):
        with self.assertRaisesRegex(ValueError, "Stale"):
            decide(self.run, "approve", "reviewer", "reviewed", "wrong")
        self.assertEqual(len(read_events(self.run)), 1)

    def test_actor_and_reason_are_required(self):
        fingerprint = digest(read_events(self.run)[0]["payload"])
        for actor, reason in (("", "reviewed"), ("reviewer", " ")):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                decide(self.run, "approve", actor, reason, fingerprint)

    def test_rejection_is_terminal(self):
        fingerprint = digest(read_events(self.run)[0]["payload"])
        decide(self.run, "reject", "reviewer", "Need more evidence", fingerprint)
        with self.assertRaises(ValueError):
            execute_run(self.run)
        with self.assertRaises(ValueError):
            self.approve()

    def test_happy_path_iterates_and_requires_new_approval_then_replays(self):
        self.approve()
        first = execute_run(self.run)
        self.assertEqual(first["feedback"]["outcome"], "not_reproduced")
        second_run = iterate_run(self.run, self.root)
        second = read_events(second_run)[0]["payload"]
        self.assertEqual(second["round"], 2)
        self.assertEqual(second["history"][0]["feedback"], first["feedback"])
        self.assertTrue(any(f["signal"] == "execution" for f in second["context"]["facts"]))
        with self.assertRaises(ValueError):
            execute_run(second_run)
        self.approve(second_run)
        self.assertEqual(execute_run(second_run)["feedback"]["outcome"], "reproduced")
        self.assertTrue(replay_run(second_run)["verified"])
        with self.assertRaisesRegex(ValueError, "stopped"):
            iterate_run(second_run, self.root)

    def test_repeated_execution_or_approval_does_not_duplicate(self):
        self.approve()
        with self.assertRaises(ValueError):
            self.approve()
        execute_run(self.run)
        with self.assertRaises(ValueError):
            execute_run(self.run)
        self.assertEqual(len(read_events(self.run)), 3)

    def test_tampering_detected_before_execution(self):
        self.approve()
        file = self.run / "0000.json"
        event = json.loads(file.read_text())
        event["payload"]["selected"]["controls"]["concurrency"] = 32
        file.write_text(json.dumps(event))
        with self.assertRaisesRegex(ValueError, "hash chain"):
            execute_run(self.run)

    def test_missing_event_rejected(self):
        self.approve()
        execute_run(self.run)
        (self.run / "0001.json").unlink()
        with self.assertRaisesRegex(ValueError, "sequence"):
            read_events(self.run)

    def test_code_version_drift_blocks_execution(self):
        self.approve()
        with patch("rarebug.workflow.code_digest", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "version changed"):
                execute_run(self.run)
        self.assertEqual(len(read_events(self.run)), 2)

    def test_lock_prevents_concurrent_decisions(self):
        with run_lock(self.run):
            with self.assertRaisesRegex(ValueError, "locked"):
                self.approve()

    def test_no_hit_exhausts_round_budget(self):
        self.spec.update(trigger_probability=0, background_probability=0)
        run = create_run(self.case, self.spec, self.root)
        for round_index in range(3):
            self.approve(run)
            execute_run(run)
            if round_index < 2:
                run = iterate_run(run, self.root)
        with self.assertRaisesRegex(ValueError, "maximum round"):
            iterate_run(run, self.root)

    def test_blocked_context_cannot_be_approved(self):
        case = load_json(DATA / "cases/conflicting_environment.json")
        spec = load_json(DATA / "simulator/conflicting_environment.json")
        run = create_run(case, spec, self.root)
        with self.assertRaisesRegex(ValueError, "pending"):
            self.approve(run)

    def test_fixture_and_simulator_must_match(self):
        self.spec["case_id"] = "different"
        with self.assertRaises(ValueError):
            create_run(self.case, self.spec, self.root)

    def test_duplicate_proposal_does_not_overwrite(self):
        with self.assertRaises(FileExistsError):
            create_run(self.case, self.spec, self.root)

    def test_report_escapes_untrusted_html_and_markdown(self):
        self.case["id"] = "<script>[click](https://attacker.example)"
        self.spec["case_id"] = self.case["id"]
        run = create_run(self.case, self.spec, self.root)
        report = render_run(run)
        self.assertNotIn("<script>", report)
        self.assertNotIn("[click]", report)
        self.assertIn("&lt;script&gt;", report)
