"""Tests for Sentinel Memory metrics wiring into Tracer."""

import os
import tempfile
import unittest

from sentinel.core.types import TraceEvent
from sentinel.monitor.tracer import Tracer


class TestTracerMetrics(unittest.TestCase):
    def test_metrics_dir_creates_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_dir = os.path.join(tmpdir, "metrics")
            tracer = Tracer(metrics_dir=metrics_dir)
            self.assertIsNotNone(tracer._metrics_store)
            self.assertTrue(os.path.exists(metrics_dir))

    def test_no_metrics_dir(self):
        tracer = Tracer()
        self.assertIsNone(tracer._metrics_store)

    def test_collect_run_metrics_no_store(self):
        tracer = Tracer()
        tracer.collect_run_metrics(files_reviewed=5)
        self.assertEqual(tracer._metrics, [])

    def test_collect_run_metrics_with_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_dir = os.path.join(tmpdir, "metrics")
            tracer = Tracer(metrics_dir=metrics_dir)

            tracer.trace(
                TraceEvent(
                    agent_name="static_analysis",
                    event="run.completed",
                    duration_ms=45.2,
                    metadata={"findings": 3, "file": "test.py"},
                )
            )
            tracer.trace(
                TraceEvent(
                    agent_name="security",
                    event="run.completed",
                    duration_ms=32.1,
                    metadata={"findings": 1, "file": "test.py"},
                )
            )
            tracer.trace(
                TraceEvent(
                    agent_name="orchestrator",
                    event="review.completed",
                    duration_ms=150.3,
                    metadata={"findings": 4, "score": 85},
                )
            )

            tracer.collect_run_metrics(
                files_reviewed=2,
                languages={"python": 2},
            )

            store = tracer._metrics_store
            runs = store.query_runs()
            self.assertEqual(len(runs), 1)

            run = runs[0]
            self.assertEqual(run.files_reviewed, 2)
            self.assertEqual(run.findings_total, 4)
            self.assertEqual(run.duration_ms, 150.3)
            self.assertEqual(run.languages, {"python": 2})
            self.assertAlmostEqual(run.agent_latencies.get("static_analysis", 0), 45.2)
            self.assertAlmostEqual(run.agent_latencies.get("security", 0), 32.1)

    def test_flush_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_dir = os.path.join(tmpdir, "metrics")
            tracer = Tracer(metrics_dir=metrics_dir)

            tracer.trace(
                TraceEvent(
                    agent_name="orchestrator",
                    event="review.completed",
                    duration_ms=100.0,
                    metadata={"findings": 0},
                )
            )

            tracer.flush_metrics()

            store = tracer._metrics_store
            runs = store.query_runs()
            self.assertEqual(len(runs), 1)

    def test_collect_empty_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_dir = os.path.join(tmpdir, "metrics")
            tracer = Tracer(metrics_dir=metrics_dir)

            tracer.collect_run_metrics(files_reviewed=0)

            store = tracer._metrics_store
            runs = store.query_runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].files_reviewed, 0)
            self.assertEqual(runs[0].findings_total, 0)


if __name__ == "__main__":
    unittest.main()
