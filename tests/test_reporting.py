"""Unit tests for reporting and tracer."""

import json
import os
import tempfile
import unittest

from sentinel.core.types import (
    AgentResult,
    AgentStatus,
    Finding,
    ReviewReport,
    Severity,
    TraceEvent,
)
from sentinel.monitor.tracer import Tracer
from sentinel.reporting.report import format_finding, to_json, to_markdown


class TestTracer(unittest.TestCase):
    def test_trace_records_events(self):
        tracer = Tracer(enabled=True)
        tracer.trace(TraceEvent(agent_name="test", event="started"))
        tracer.trace(TraceEvent(agent_name="test", event="completed"))
        self.assertEqual(len(tracer.get_events()), 2)

    def test_disabled_tracer(self):
        tracer = Tracer(enabled=False)
        tracer.trace(TraceEvent(agent_name="test", event="started"))
        self.assertEqual(len(tracer.get_events()), 0)

    def test_metric_recording(self):
        tracer = Tracer(enabled=True)
        tracer.metric("review_time_ms", 150.0, {"file": "test.py"})
        self.assertEqual(len(tracer.get_metrics()), 1)
        self.assertEqual(tracer.get_metrics()[0].value, 150.0)

    def test_summary_empty(self):
        tracer = Tracer()
        summary = tracer.summary()
        self.assertEqual(summary["total_events"], 0)
        self.assertEqual(summary["total_metrics"], 0)

    def test_summary_with_events(self):
        tracer = Tracer(enabled=True)
        tracer.trace(TraceEvent(agent_name="a1", event="run.completed", duration_ms=10.0))
        tracer.trace(TraceEvent(agent_name="a2", event="run.completed", duration_ms=20.0))
        summary = tracer.summary()
        self.assertEqual(summary["total_events"], 2)
        self.assertIn("a1", summary["agent_durations_ms"])

    def test_export_trace(self):
        tracer = Tracer(enabled=True)
        tracer.trace(TraceEvent(agent_name="test", event="run.started"))
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = f.name
        try:
            tracer.export_trace(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("events", data)
            self.assertEqual(len(data["events"]), 1)
        finally:
            os.unlink(path)

    def test_flush_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = Tracer(log_dir=tmpdir, enabled=True)
            tracer.trace(TraceEvent(agent_name="test", event="run.started"))
            tracer.flush()
            files = os.listdir(tmpdir)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].startswith("trace_"))


class TestReportFormatting(unittest.TestCase):
    def setUp(self):
        self.finding = Finding(
            agent_name="test",
            severity=Severity.HIGH,
            message="test issue",
            suggestion="fix it",
            file="test.py",
            line=42,
            rule_id="TST001",
        )

    def test_format_finding(self):
        output = format_finding(self.finding)
        self.assertIn("test issue", output)
        self.assertIn("test.py:42", output)
        self.assertIn("fix it", output)

    def test_format_finding_no_line(self):
        f = Finding(
            agent_name="test",
            severity=Severity.INFO,
            message="general issue",
            file="test.py",
        )
        output = format_finding(f)
        self.assertIn("test.py", output)

    def test_to_markdown_empty(self):
        report = ReviewReport()
        output = to_markdown(report, "## Summary\n")
        self.assertIn("Code Review Report", output)
        self.assertIn("No issues found", output)

    def test_to_markdown_with_findings(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[self.finding],
        )
        report.agent_results.append(result)
        output = to_markdown(report, "## Summary\n")
        self.assertIn("test issue", output)
        self.assertIn("Detailed Findings", output)

    def test_to_json_structure(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[self.finding],
        )
        report.agent_results.append(result)
        output = to_json(report, "summary text")
        data = json.loads(output)
        self.assertIn("id", data)
        self.assertIn("score", data)
        self.assertIn("findings", data)
        self.assertEqual(len(data["findings"]), 1)
        self.assertEqual(data["findings"][0]["message"], "test issue")

    def test_to_json_agent_results(self):
        report = ReviewReport()
        result = AgentResult(
            agent_name="security",
            status=AgentStatus.FAILED,
            error="something broke",
        )
        report.agent_results.append(result)
        output = to_json(report, "")
        data = json.loads(output)
        self.assertEqual(len(data["agent_results"]), 1)
        self.assertEqual(data["agent_results"][0]["error"], "something broke")


if __name__ == "__main__":
    unittest.main()
