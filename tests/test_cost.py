"""Tests for cost governance (ADLC Govern phase)."""

import unittest

from sentinel.govern.cost import DEFAULT_COST_RATES, CostEntry, CostReport, CostTracker


class TestCostReport(unittest.TestCase):
    def test_empty_report(self):
        r = CostReport()
        self.assertEqual(r.total_cost, 0)
        self.assertEqual(r.total_duration_ms, 0)
        self.assertEqual(len(r.entries), 0)

    def test_add_entry(self):
        r = CostReport()
        r.add("static-analysis", 100.0, 0.0)
        self.assertEqual(len(r.entries), 1)
        self.assertEqual(r.entries[0].cost, 0.0)

    def test_add_entry_with_cost(self):
        r = CostReport()
        r.add("llm-agent", 1000.0, 0.0001)
        self.assertAlmostEqual(r.total_cost, 0.1)

    def test_to_dict(self):
        r = CostReport()
        r.add("agent-x", 50.0, 0.001)
        d = r.to_dict()
        self.assertIn("total_cost", d)
        self.assertIn("entries", d)
        self.assertEqual(len(d["entries"]), 1)

    def test_summary_line(self):
        r = CostReport()
        r.add("test", 100.0, 0.0)
        line = r.summary_line()
        self.assertIn("Cost:", line)
        self.assertIn("0.000000", line)


class TestCostEntry(unittest.TestCase):
    def test_cost_calculation(self):
        e = CostEntry(agent_name="test", duration_ms=500, rate_per_ms=0.0001, cost=0)
        self.assertEqual(e.cost, 0.05)

    def test_zero_cost(self):
        e = CostEntry(agent_name="test", duration_ms=500, rate_per_ms=0.0, cost=0)
        self.assertEqual(e.cost, 0.0)


class TestCostTracker(unittest.TestCase):
    def test_default_rates(self):
        t = CostTracker()
        self.assertEqual(t._rates["static-analysis"], 0.0)
        self.assertEqual(t._rates["security"], 0.0)

    def test_custom_rates(self):
        t = CostTracker(custom_rates={"llm-agent": 0.001})
        self.assertEqual(t._rates["llm-agent"], 0.001)
        self.assertEqual(t._rates["static-analysis"], 0.0)  # default preserved

    def test_track_static(self):
        t = CostTracker()
        t.track("static-analysis", 100.0)
        self.assertEqual(t.total_cost, 0.0)

    def test_track_with_cost(self):
        t = CostTracker()
        t.track("llm-agent", 1000.0, 0.0001)
        self.assertAlmostEqual(t.total_cost, 0.1)

    def test_cap_not_exceeded(self):
        t = CostTracker(cost_cap=1.0)
        t.track("static-analysis", 100.0)
        self.assertFalse(t.cap_exceeded)

    def test_cap_exceeded(self):
        t = CostTracker(cost_cap=0.05)
        t.track("llm-agent", 1000.0, 0.0001)
        self.assertTrue(t.cap_exceeded)

    def test_no_cap(self):
        t = CostTracker()
        self.assertFalse(t.cap_exceeded)

    def test_track_disabled(self):
        t = CostTracker(enabled=False)
        t.track("static-analysis", 100.0)
        self.assertEqual(t.total_cost, 0.0)

    def test_reset(self):
        t = CostTracker()
        t.track("static-analysis", 100.0)
        self.assertEqual(len(t.report.entries), 1)
        t.reset()
        self.assertEqual(len(t.report.entries), 0)

    def test_report_property(self):
        t = CostTracker()
        self.assertIsNotNone(t.report)
        self.assertEqual(t.report.total_cost, 0)

    def test_default_rates_dict(self):
        self.assertIn("static-analysis", DEFAULT_COST_RATES)
        self.assertIn("security", DEFAULT_COST_RATES)
        self.assertIn("style", DEFAULT_COST_RATES)
        self.assertIn("best-practices", DEFAULT_COST_RATES)
        self.assertIn("documentation", DEFAULT_COST_RATES)
        self.assertEqual(len(DEFAULT_COST_RATES), 5)


if __name__ == "__main__":
    unittest.main()
