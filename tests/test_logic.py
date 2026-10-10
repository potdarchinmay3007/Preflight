"""Logic tests. Run from the project folder: python -m unittest discover -s tests -v"""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import server as s


class Backtest(unittest.TestCase):
    def test_planted_signals(self):
        self.assertTrue(s.backtest_signal("first_gtm_hire")["verdict"].startswith("KEEP"))
        r = s.backtest_signal("conference_attendee")
        self.assertTrue(r["verdict"].startswith("DROP"))
        self.assertAlmostEqual(r["lift"], 0.44, places=2)

    def test_bad_inputs(self):
        self.assertIn("error", s.backtest_signal("nope"))
        for w in (0, -5, 91):
            self.assertIn("error", s.backtest_signal("first_gtm_hire", w))

    def test_wilson(self):
        lo, hi = s.wilson(50, 100)
        self.assertLess(lo, 0.5); self.assertGreater(hi, 0.5)
        self.assertEqual(s.wilson(0, 0), (0.0, 0.0))


class Simulate(unittest.TestCase):
    def test_name_normalisation(self):
        self.assertEqual(s._norm("Acme Inc"), s._norm("ACME, Inc."))

    def test_unknown_inputs(self):
        self.assertIn("error", s.simulate_agent_run("nope"))
        self.assertIn("error", s.simulate_agent_run("conference_followup", ["A999"]))

    def test_policy_context_is_small(self):
        r = s.simulate_agent_run("conference_followup")
        self.assertGreater(r["blockers"] + r["warnings"], 0)
        c = r["policy_context"]
        self.assertEqual(c["chunks_returned"], 3)
        self.assertLess(c["tokens_returned"], c["tokens_all_policy_docs"])

    def test_retrieval_finds_right_doc(self):
        top = s.search_policy("contacted within seven days minimum gap")["chunks"][0]
        self.assertEqual(top["source"], "contact_frequency_policy.md")


class Decide(unittest.TestCase):
    def setUp(self):
        self._audit = s.AUDIT
        s.AUDIT = Path(tempfile.mkdtemp()) / "audit.jsonl"
        self.blocked = next(r for r in s.RUNS if any(
            i["type"] == "BLOCK" for i in s._simulate(s.RUNS[r]["agent"], s.RUNS[r]["account_ids"])))

    def tearDown(self):
        s.AUDIT = self._audit

    def test_reason_required(self):
        self.assertIn("error", s.decide_launch(self.blocked, "approve", "  "))
        self.assertIn("error", s.decide_launch(self.blocked, "maybe", "x"))

    def test_approve_refused_with_blockers(self):
        self.assertEqual(s.decide_launch(self.blocked, "approve", "ok")["status"], "REFUSED")
        self.assertFalse(s.AUDIT.exists())

    def test_reject_recorded(self):
        self.assertEqual(s.decide_launch(self.blocked, "reject", "too risky")["status"], "RECORDED")
        self.assertTrue(s.AUDIT.exists())

    def test_approve_recorded_without_blockers(self):
        orig, s._simulate = s._simulate, lambda *a: []
        try:
            self.assertEqual(s.decide_launch(self.blocked, "approve", "reviewed")["status"], "RECORDED")
        finally:
            s._simulate = orig


if __name__ == "__main__":
    unittest.main()
