"""Unit tests for the orchestrator."""

import unittest

from sentinel.agents.static_analysis import StaticAnalysisAgent
from sentinel.core.context import ReviewContext
from sentinel.core.orchestrator import Orchestrator
from sentinel.core.types import FileContext
from sentinel.monitor.tracer import Tracer


class TestOrchestrator(unittest.TestCase):
    def test_review_empty_context(self):
        orch = Orchestrator()
        ctx = ReviewContext()
        report = orch.review(ctx)
        self.assertEqual(len(report.files_reviewed), 0)

    def test_review_single_file(self):
        orch = Orchestrator()
        ctx = ReviewContext(files=[FileContext(path="test.py", content="x = 1")])
        report = orch.review(ctx)
        self.assertEqual(len(report.files_reviewed), 1)
        self.assertGreaterEqual(len(report.agent_results), 4)

    def test_review_with_all_agents_enabled(self):
        orch = Orchestrator()
        ctx = ReviewContext.from_file("test.py", 'password = "secret"')
        report = orch.review(ctx)
        all_findings = report.all_findings
        agent_names = {f.agent_name for f in all_findings}
        self.assertIn("security", agent_names)

    def test_review_with_custom_agents(self):
        agent = StaticAnalysisAgent()
        orch = Orchestrator(agents=[agent])
        ctx = ReviewContext.from_file("test.py", "x = 1")
        report = orch.review(ctx)
        self.assertEqual(len(report.agent_results), 1)
        self.assertIn("static-analysis", report.agent_results[0].agent_name)

    def test_review_records_traces(self):
        tracer = Tracer(enabled=True)
        orch = Orchestrator(tracer=tracer)
        ctx = ReviewContext.from_file("test.py", "x = 1")
        orch.review(ctx)
        events = tracer.get_events()
        self.assertGreater(len(events), 0)
        event_names = {e.event for e in events}
        self.assertIn("review.started", event_names)
        self.assertIn("review.completed", event_names)

    def test_summarize_returns_string(self):
        from sentinel.core.types import ReviewReport

        orch = Orchestrator()
        report = ReviewReport()
        summary = orch.summarize(report)
        self.assertIsInstance(summary, str)
        self.assertIn("Score", summary)

    def test_get_agent_report_found(self):
        orch = Orchestrator()
        ctx = ReviewContext.from_file("test.py", "x = 1")
        report = orch.review(ctx)
        result = orch.get_agent_report("static-analysis", report)
        self.assertIsNotNone(result)
        self.assertEqual(result.agent_name, "static-analysis")

    def test_get_agent_report_not_found(self):
        orch = Orchestrator()
        from sentinel.core.types import ReviewReport

        report = ReviewReport()
        result = orch.get_agent_report("nonexistent", report)
        self.assertIsNone(result)


class TestOrchestratorWithBadCode(unittest.TestCase):
    def test_bad_code_issues_detected(self):
        bad_code = """import os
import sys
password = "secret"
eval("os.system('ls')")
"""
        orch = Orchestrator()
        ctx = ReviewContext.from_file("bad.py", bad_code)
        report = orch.review(ctx)
        self.assertGreaterEqual(len(report.all_findings), 5)
        self.assertLess(report.score, 50)

    def test_good_code_minimal_findings(self):
        good_code = '"""Module docstring."""\n\nx = 1\ny = 2\nz = x + y\n'
        orch = Orchestrator()
        ctx = ReviewContext.from_file("good.py", good_code)
        report = orch.review(ctx)
        self.assertGreaterEqual(report.score, 70)


if __name__ == "__main__":
    unittest.main()
