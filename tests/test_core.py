"""Unit tests for core/ types, base_agent, context."""

import time
import unittest

from sentinel.core.base_agent import BaseAgent
from sentinel.core.context import ReviewContext
from sentinel.core.types import (
    AgentResult,
    AgentStatus,
    Feedback,
    FeedbackRating,
    FeedbackType,
    FileContext,
    Finding,
    ReviewReport,
    ReviewScope,
    Severity,
)


class TestSeverity(unittest.TestCase):
    def test_severity_ordering(self):
        order = list(Severity)
        self.assertLess(order.index(Severity.CRITICAL), order.index(Severity.HIGH))
        self.assertLess(order.index(Severity.HIGH), order.index(Severity.MEDIUM))
        self.assertLess(order.index(Severity.MEDIUM), order.index(Severity.LOW))
        self.assertLess(order.index(Severity.LOW), order.index(Severity.INFO))


class TestFinding(unittest.TestCase):
    def test_finding_defaults(self):
        f = Finding()
        self.assertEqual(len(f.id), 8)
        self.assertEqual(f.severity, Severity.INFO)

    def test_finding_with_values(self):
        f = Finding(
            agent_name="test-agent",
            severity=Severity.HIGH,
            message="test issue",
            suggestion="fix it",
            file="test.py",
            line=42,
        )
        self.assertEqual(f.agent_name, "test-agent")
        self.assertEqual(f.severity, Severity.HIGH)
        self.assertEqual(f.line, 42)


class TestReviewReport(unittest.TestCase):
    def test_empty_report_score(self):
        report = ReviewReport()
        self.assertEqual(report.score, 100)

    def test_report_score_with_findings(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[
                Finding(severity=Severity.CRITICAL),
                Finding(severity=Severity.HIGH),
                Finding(severity=Severity.MEDIUM),
            ],
        )
        report.agent_results.append(result)
        self.assertLess(report.score, 100)

    def test_all_findings_sorted_by_severity(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[
                Finding(severity=Severity.INFO, message="info"),
                Finding(severity=Severity.CRITICAL, message="critical"),
                Finding(severity=Severity.MEDIUM, message="medium"),
            ],
        )
        report.agent_results.append(result)
        findings = report.all_findings
        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0].severity, Severity.CRITICAL)
        self.assertEqual(findings[1].severity, Severity.MEDIUM)
        self.assertEqual(findings[2].severity, Severity.INFO)

    def test_score_never_negative(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[Finding(severity=Severity.CRITICAL) for _ in range(100)],
        )
        report.agent_results.append(result)
        self.assertGreaterEqual(report.score, 0)


class TestBaseAgent(unittest.TestCase):
    def test_enabled_agent_runs(self):
        class TestAgent(BaseAgent):
            def analyze(self, file):
                return [Finding(message="test")]

        agent = TestAgent("test-agent")
        file = FileContext(path="test.py", content="x = 1")
        result = agent.run(file)
        self.assertEqual(result.status, AgentStatus.COMPLETED)
        self.assertEqual(len(result.findings), 1)

    def test_disabled_agent_skips(self):
        class TestAgent(BaseAgent):
            def analyze(self, file):
                return [Finding(message="should not appear")]

        agent = TestAgent("test-agent", enabled=False)
        file = FileContext(path="test.py", content="x = 1")
        result = agent.run(file)
        self.assertEqual(result.status, AgentStatus.COMPLETED)
        self.assertEqual(len(result.findings), 0)

    def test_agent_catches_exceptions(self):
        class BrokenAgent(BaseAgent):
            def analyze(self, file):
                raise ValueError("something broke")

        agent = BrokenAgent("broken")
        file = FileContext(path="test.py", content="x = 1")
        result = agent.run(file)
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIn("something broke", result.error or "")

    def test_agent_records_duration(self):
        class TestAgent(BaseAgent):
            def analyze(self, file):
                time.sleep(0.01)
                return []

        agent = TestAgent("slow")
        file = FileContext(path="test.py", content="x = 1")
        result = agent.run(file)
        self.assertGreater(result.duration_ms, 5)


class TestReviewContext(unittest.TestCase):
    def test_from_file(self):
        ctx = ReviewContext.from_file("test.py", "print('hello')")
        self.assertEqual(len(ctx.files), 1)
        self.assertEqual(ctx.files[0].path, "test.py")
        self.assertEqual(ctx.scope, ReviewScope.FULL_FILE)

    def test_from_diff(self):
        ctx = ReviewContext.from_diff([("file1.py", "a=1"), ("file2.py", "b=2")])
        self.assertEqual(len(ctx.files), 2)
        self.assertEqual(ctx.scope, ReviewScope.DIFF)

    def test_default_config(self):
        ctx = ReviewContext()
        self.assertIn("max_line_length", ctx.config)
        self.assertIn("complexity_threshold", ctx.config)


class TestFeedback(unittest.TestCase):
    def test_feedback_defaults(self):
        fb = Feedback(finding_id="abc123")
        self.assertEqual(fb.finding_id, "abc123")
        self.assertEqual(fb.feedback_type, FeedbackType.HUMAN)
        self.assertEqual(fb.rating, FeedbackRating.UNSURE)
        self.assertEqual(fb.comment, "")
        self.assertIsNotNone(fb.timestamp)

    def test_feedback_custom(self):
        fb = Feedback(
            finding_id="xyz",
            trace_file="trace_123.json",
            feedback_type=FeedbackType.LLM,
            rating=FeedbackRating.CORRECT,
            comment="Valid finding",
        )
        self.assertEqual(fb.finding_id, "xyz")
        self.assertEqual(fb.trace_file, "trace_123.json")
        self.assertEqual(fb.feedback_type, FeedbackType.LLM)
        self.assertEqual(fb.rating, FeedbackRating.CORRECT)
        self.assertEqual(fb.comment, "Valid finding")

    def test_finding_reviewed_default(self):
        f = Finding()
        self.assertFalse(f.reviewed)


if __name__ == "__main__":
    unittest.main()
