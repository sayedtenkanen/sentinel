"""Tests for tracer feedback pipeline."""

import json
import os
import tempfile
import unittest

from sentinel.core.types import Feedback, FeedbackRating, FeedbackType
from sentinel.monitor.tracer import Tracer


class TestTracerFeedback(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_store_and_retrieve_feedback(self):
        tracer = Tracer(enabled=True)
        fb = Feedback(finding_id="abc", rating=FeedbackRating.CORRECT)
        tracer.store_feedback(fb)
        feedbacks = tracer.get_feedback()
        self.assertEqual(len(feedbacks), 1)
        self.assertEqual(feedbacks[0].finding_id, "abc")
        self.assertEqual(feedbacks[0].rating, FeedbackRating.CORRECT)

    def test_feedback_disabled_tracer(self):
        tracer = Tracer(enabled=False)
        fb = Feedback(finding_id="abc")
        tracer.store_feedback(fb)
        self.assertEqual(len(tracer.get_feedback()), 0)

    def test_export_feedback_to_disk(self):
        tracer = Tracer(enabled=True, feedback_dir=self.tmpdir)
        fb = Feedback(
            finding_id="test123",
            trace_file="trace_001.json",
            feedback_type=FeedbackType.HUMAN,
            rating=FeedbackRating.INCORRECT,
            comment="False positive",
        )
        tracer.store_feedback(fb)
        path = tracer.export_feedback("trace_001.json")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["finding_id"], "test123")
        self.assertEqual(data[0]["rating"], "incorrect")
        self.assertEqual(data[0]["comment"], "False positive")

    def test_export_feedback_no_feedbacks(self):
        tracer = Tracer(enabled=True, feedback_dir=self.tmpdir)
        path = tracer.export_feedback("trace_001.json")
        self.assertIsNone(path)

    def test_flush_includes_feedback(self):
        tracer = Tracer(enabled=True, log_dir=self.tmpdir)
        fb = Feedback(
            finding_id="flush_test",
            feedback_type=FeedbackType.LLM,
            rating=FeedbackRating.CORRECT,
        )
        tracer.store_feedback(fb)
        tracer.flush()
        trace_files = [f for f in os.listdir(self.tmpdir) if f.startswith("trace_")]
        feedback_files = [f for f in os.listdir(self.tmpdir) if f.startswith("feedback_")]
        self.assertEqual(len(trace_files), 1)
        self.assertEqual(len(feedback_files), 1)
        with open(os.path.join(self.tmpdir, trace_files[0])) as f:
            trace_data = json.load(f)
        self.assertIn("feedbacks", trace_data)
        self.assertEqual(len(trace_data["feedbacks"]), 1)
        self.assertEqual(trace_data["feedbacks"][0]["finding_id"], "flush_test")

    def test_export_trace_with_feedbacks(self):
        tracer = Tracer(enabled=True)
        fb = Feedback(
            finding_id="trace_fb", feedback_type=FeedbackType.HUMAN, rating=FeedbackRating.UNSURE
        )
        tracer.store_feedback(fb)
        path = os.path.join(self.tmpdir, "export_test.json")
        tracer.export_trace(path)
        with open(path) as f:
            data = json.load(f)
        self.assertIn("feedbacks", data)
        self.assertEqual(len(data["feedbacks"]), 1)
        self.assertEqual(data["feedbacks"][0]["finding_id"], "trace_fb")


class TestTracerSummary(unittest.TestCase):
    def test_summary_with_feedback(self):
        tracer = Tracer(enabled=True)
        fb = Feedback(finding_id="s1", comment="Looks good")
        tracer.store_feedback(fb)
        summary = tracer.summary()
        self.assertIn("total_events", summary)

    def test_summary_empty(self):
        tracer = Tracer(enabled=True)
        summary = tracer.summary()
        self.assertEqual(summary["total_events"], 0)
        self.assertEqual(summary["total_metrics"], 0)

    def test_summary_with_failed_events(self):
        from sentinel.core.types import TraceEvent

        tracer = Tracer(enabled=True)
        tracer.trace(
            TraceEvent(agent_name="agent1", event="run.failed", metadata={"error": "boom"})
        )
        summary = tracer.summary()
        self.assertIn("errors", summary)
        self.assertEqual(len(summary["errors"]), 1)
        self.assertIn("boom", summary["errors"][0])

    def test_metric_disabled(self):
        tracer = Tracer(enabled=False)
        tracer.metric("test", 1.0)
        self.assertEqual(len(tracer.get_metrics()), 0)

    def test_export_feedback_no_dir(self):
        tracer = Tracer(enabled=True, feedback_dir=None)
        fb = Feedback(finding_id="test")
        tracer.store_feedback(fb)
        path = tracer.export_feedback("trace.json")
        self.assertIsNone(path)

    def test_flush_no_log_dir(self):
        tracer = Tracer(enabled=True, log_dir=None)
        tracer.flush()

    def test_metric_enabled(self):
        tracer = Tracer(enabled=True)
        tracer.metric("latency", 42.0, {"agent": "style"})
        metrics = tracer.get_metrics()
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].name, "latency")
        self.assertEqual(metrics[0].value, 42.0)

    def test_flush_with_log_dir_writes_trace_files(self):
        with tempfile.TemporaryDirectory() as log_dir:
            tracer = Tracer(enabled=True, log_dir=log_dir)
            tracer.metric("latency", 10.0, {"agent": "unit-test"})
            tracer.flush()
            files = os.listdir(log_dir)
            self.assertGreater(len(files), 0)
            for filename in files:
                path = os.path.join(log_dir, filename)
                self.assertTrue(os.path.isfile(path))

    def test_export_feedback_with_dir(self):
        with tempfile.TemporaryDirectory() as feedback_dir:
            tracer = Tracer(enabled=True, feedback_dir=feedback_dir)
            fb = Feedback(finding_id="test")
            tracer.store_feedback(fb)
            path = tracer.export_feedback("trace.json")
            self.assertIsNotNone(path)
            self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
