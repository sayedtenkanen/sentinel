import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sentinel.monitor.dashboard import (
    DashboardConfig,
    _summarize_trace,
    _summary_cards_html,
    build_html,
    build_summary_stats,
    load_feedbacks,
    load_traces,
)


class TestLoadTraces(unittest.TestCase):
    def test_missing_dir(self):
        self.assertEqual(load_traces("/nonexistent/path"), [])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_traces(d), [])

    def test_loads_valid_traces(self):
        with tempfile.TemporaryDirectory() as d:
            trace = {"events": [], "agents": ["style"]}
            path = os.path.join(d, "trace_test.json")
            with open(path, "w") as f:
                json.dump(trace, f)
            result = load_traces(d)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["agents"], ["style"])
            self.assertIn("_filename", result[0])
            self.assertIn("_filetime", result[0])

    def test_skips_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace_bad.json")
            with open(path, "w") as f:
                f.write("not json")
            result = load_traces(d)
            self.assertEqual(result, [])

    def test_reverse_sort_order(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["trace_b.json", "trace_a.json"]:
                path = os.path.join(d, name)
                with open(path, "w") as f:
                    json.dump({"file": name}, f)
            result = load_traces(d)
            self.assertEqual(len(result), 2)
            self.assertTrue(result[0]["_filename"] >= result[1]["_filename"])


class TestLoadFeedbacks(unittest.TestCase):
    def test_missing_dir(self):
        self.assertEqual(load_feedbacks("/nonexistent"), [])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_feedbacks(d), [])

    def test_loads_single_dict_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            fb = {"finding_id": "x", "rating": "correct"}
            path = os.path.join(d, "feedback_trace_x.json")
            with open(path, "w") as f:
                json.dump(fb, f)
            result = load_feedbacks(d)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["finding_id"], "x")

    def test_loads_list_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            fbs = [{"finding_id": "a"}, {"finding_id": "b"}]
            path = os.path.join(d, "feedback_trace_x.json")
            with open(path, "w") as f:
                json.dump(fbs, f)
            result = load_feedbacks(d)
            self.assertEqual(len(result), 2)

    def test_skips_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "feedback_trace_x.json")
            with open(path, "w") as f:
                f.write("bad")
            result = load_feedbacks(d)
            self.assertEqual(result, [])

    def test_ignores_non_feedback_files(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace_x.json")
            with open(path, "w") as f:
                json.dump({}, f)
            result = load_feedbacks(d)
            self.assertEqual(result, [])


class TestSummarizeTrace(unittest.TestCase):
    def test_empty_trace(self):
        result = _summarize_trace({"events": []})
        self.assertEqual(result["duration"], 0.0)
        self.assertEqual(result["findings"], 0)
        self.assertEqual(result["agent_totals"], {})
        self.assertEqual(result["agent_counts"], {})

    def test_no_events_key(self):
        result = _summarize_trace({})
        self.assertEqual(result["duration"], 0.0)
        self.assertEqual(result["findings"], 0)

    def test_accumulates_agent_totals(self):
        trace = {
            "events": [
                {"agent": "style", "duration_ms": 10.0, "event": "review.completed", "metadata": {"findings": 3}},
                {"agent": "security", "duration_ms": 20.0, "event": "agent.completed", "metadata": {}},
                {"agent": "style", "duration_ms": 5.0, "event": "agent.started", "metadata": {}},
            ]
        }
        result = _summarize_trace(trace)
        self.assertAlmostEqual(result["duration"], 35.0)
        self.assertEqual(result["findings"], 3)
        self.assertAlmostEqual(result["agent_totals"]["style"], 15.0)
        self.assertAlmostEqual(result["agent_totals"]["security"], 20.0)
        self.assertEqual(result["agent_counts"]["style"], 2)
        self.assertEqual(result["agent_counts"]["security"], 1)

    def test_handles_none_metadata(self):
        trace = {
            "events": [
                {"agent": "x", "duration_ms": 5.0, "event": "review.completed", "metadata": None},
            ]
        }
        result = _summarize_trace(trace)
        self.assertEqual(result["findings"], 0)


class TestBuildSummaryStats(unittest.TestCase):
    def test_empty_traces(self):
        stats = build_summary_stats([])
        self.assertEqual(stats["total_reviews"], 0)
        self.assertEqual(stats["total_events"], 0)
        self.assertEqual(stats["total_duration_ms"], 0.0)
        self.assertEqual(stats["traces_with_findings"], 0)
        self.assertEqual(stats["agent_totals"], {})
        self.assertEqual(stats["findings_over_time"], [])
        self.assertEqual(stats["recent_traces"], [])

    def test_aggregates_traces(self):
        traces = [
            {
                "_filename": "trace_a.json",
                "_filetime": "2025-01-01",
                "events": [
                    {"agent": "style", "duration_ms": 10.0, "event": "review.completed", "metadata": {"findings": 2}},
                ],
            },
            {
                "_filename": "trace_b.json",
                "_filetime": "2025-01-02",
                "events": [
                    {"agent": "security", "duration_ms": 5.0, "event": "review.completed", "metadata": {"findings": 0}},
                ],
            },
        ]
        stats = build_summary_stats(traces)
        self.assertEqual(stats["total_reviews"], 2)
        self.assertEqual(stats["total_events"], 2)
        self.assertAlmostEqual(stats["total_duration_ms"], 15.0)
        self.assertEqual(stats["traces_with_findings"], 1)
        self.assertAlmostEqual(stats["agent_totals"]["style"], 10.0)
        self.assertAlmostEqual(stats["agent_totals"]["security"], 5.0)
        self.assertEqual(len(stats["findings_over_time"]), 2)
        self.assertEqual(len(stats["recent_traces"]), 2)

    def test_recent_traces_limited_to_20(self):
        traces = [{"_filename": f"trace_{i}.json", "_filetime": "", "events": []} for i in range(25)]
        stats = build_summary_stats(traces)
        self.assertEqual(len(stats["recent_traces"]), 20)


class TestBuildHtml(unittest.TestCase):
    def test_contains_required_sections(self):
        stats = {
            "total_reviews": 5,
            "total_events": 100,
            "total_duration_ms": 500.0,
            "traces_with_findings": 3,
            "agent_totals": {"style": 300.0},
            "findings_over_time": [],
            "recent_traces": [],
        }
        html = build_html(stats)
        self.assertIn("Code Review Dashboard", html)
        self.assertIn("Total Reviews", html)
        self.assertIn("Agent Duration Breakdown", html)
        self.assertIn("Trend (Last 50 Reviews)", html)
        self.assertIn("Recent Traces", html)
        self.assertIn("Feedback", html)
        self.assertIn("agents =", html)
        self.assertIn("timeline =", html)
        self.assertIn("recent =", html)
        self.assertIn("feedbacks =", html)

    def test_includes_feedbacks_json(self):
        stats = {
            "total_reviews": 0,
            "total_events": 0,
            "total_duration_ms": 0.0,
            "traces_with_findings": 0,
            "agent_totals": {},
            "findings_over_time": [],
            "recent_traces": [],
        }
        feedbacks = [{"finding_id": "x", "rating": "correct"}]
        html = build_html(stats, feedbacks)
        self.assertIn("correct", html)
        self.assertIn("finding_id", html)


class TestSummaryCardsHtml(unittest.TestCase):
    def test_generates_four_cards(self):
        stats = {
            "total_reviews": 10,
            "total_events": 50,
            "total_duration_ms": 1000.0,
            "traces_with_findings": 7,
        }
        html = _summary_cards_html(stats)
        self.assertIn("Total Reviews", html)
        self.assertIn("Total Events", html)
        self.assertIn("Total Duration", html)
        self.assertIn("Reviews w/ Findings", html)
        self.assertIn("grid", html)
        self.assertIn("card", html)
        self.assertIn("10", html)
        self.assertIn("1000ms", html)


class TestDashboardConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = DashboardConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 8080)
        self.assertEqual(cfg.trace_dir, "./traces")
        self.assertFalse(cfg.open_browser)

    def test_from_args_parses_flags(self):
        cfg = DashboardConfig.from_args(["--port", "9090", "--host", "0.0.0.0", "--trace-dir", "/tmp/traces", "--open"])
        self.assertEqual(cfg.port, 9090)
        self.assertEqual(cfg.host, "0.0.0.0")
        self.assertEqual(cfg.trace_dir, "/tmp/traces")
        self.assertTrue(cfg.open_browser)

    def test_from_args_defaults_when_empty(self):
        cfg = DashboardConfig.from_args([])
        self.assertEqual(cfg.port, 8080)
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.trace_dir, "./traces")
        self.assertFalse(cfg.open_browser)

    def test_from_args_handles_none(self):
        cfg = DashboardConfig.from_args(None)
        self.assertEqual(cfg.port, 8080)


class TestDashboardHandler(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        trace = {"events": [], "agents": ["style"]}
        with open(os.path.join(self.tmpdir, "trace_test.json"), "w") as f:
            json.dump(trace, f)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _make_handler(self, path="/", method="GET"):
        from sentinel.monitor.dashboard import DashboardHandler

        handler = DashboardHandler.__new__(DashboardHandler)
        handler.config = DashboardConfig(trace_dir=self.tmpdir)
        handler.path = path
        handler.command = method
        handler.headers = {"Content-Length": "0"}
        handler.rfile = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        return handler

    def test_do_get_api_stats(self):
        handler = self._make_handler("/api/stats")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)

    def test_do_get_api_traces(self):
        handler = self._make_handler("/api/traces")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)

    def test_do_get_api_feedback(self):
        handler = self._make_handler("/api/feedback")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)

    def test_do_get_html_page(self):
        handler = self._make_handler("/")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        sent_data = handler.wfile.write.call_args[0][0].decode()
        self.assertIn("Code Review Dashboard", sent_data)

    def test_do_post_feedback(self):
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "50"}
        handler.rfile.read.return_value = json.dumps({
            "trace_file": "test.json",
            "finding_id": "SEC001",
            "rating": "correct",
            "comment": "good",
        }).encode()
        handler.do_POST()
        handler.send_response.assert_called_once_with(200)
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "ok")

    def test_do_post_feedback_appends_existing(self):
        existing_path = os.path.join(self.tmpdir, "feedback_test.json")
        with open(existing_path, "w") as f:
            json.dump([{"finding_id": "old", "rating": "incorrect"}], f)
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "50"}
        handler.rfile.read.return_value = json.dumps({
            "trace_file": "test.json",
            "finding_id": "new",
            "rating": "correct",
        }).encode()
        handler.do_POST()
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "ok")
        self.assertEqual(sent_data["feedback"]["finding_id"], "new")

    def test_do_post_feedback_handles_single_dict(self):
        existing_path = os.path.join(self.tmpdir, "feedback_test.json")
        with open(existing_path, "w") as f:
            json.dump({"finding_id": "old", "rating": "incorrect"}, f)
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "50"}
        handler.rfile.read.return_value = json.dumps({
            "trace_file": "test.json",
            "finding_id": "new",
            "rating": "correct",
        }).encode()
        handler.do_POST()
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "ok")

    def test_do_post_feedback_empty_body(self):
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "0"}
        handler.do_POST()
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "error")
        self.assertIn("Empty body", sent_data["message"])

    def test_do_post_feedback_invalid_json(self):
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "5"}
        handler.rfile.read.return_value = b"bad:{"
        handler.do_POST()
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "error")
        self.assertIn("Invalid JSON", sent_data["message"])

    def test_do_post_feedback_missing_trace_file(self):
        handler = self._make_handler("/api/feedback", "POST")
        handler.headers = {"Content-Length": "20"}
        handler.rfile.read.return_value = json.dumps({"other": "data"}).encode()
        handler.do_POST()
        sent_data = json.loads(handler.wfile.write.call_args[0][0])
        self.assertEqual(sent_data["status"], "error")
        self.assertIn("trace_file is required", sent_data["message"])

    def test_do_post_not_feedback_path(self):
        handler = self._make_handler("/api/other", "POST")
        handler.do_POST()
        handler.send_response.assert_called_once_with(404)

    def test_log_message_suppresses_get(self):
        handler = self._make_handler("/", "GET")
        with patch("http.server.BaseHTTPRequestHandler.log_message") as mock_super:
            handler.log_message("%s %s", "GET", "/")
            mock_super.assert_not_called()

    def test_log_message_passes_non_get(self):
        handler = self._make_handler("/", "POST")
        with patch("http.server.BaseHTTPRequestHandler.log_message") as mock_super:
            handler.log_message("%s %s", "POST", "/")
            mock_super.assert_called_once()


class TestMainFunction(unittest.TestCase):
    @patch("sentinel.monitor.dashboard.http.server.HTTPServer")
    def test_main_starts_server(self, mock_server_class):
        from sentinel.monitor.dashboard import main

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        result = main(["--port", "9999", "--trace-dir", "/tmp"])
        self.assertEqual(result, 0)
        mock_server_class.assert_called_once()
        mock_server.serve_forever.assert_called_once()
        mock_server.shutdown.assert_called_once()

    @patch("sentinel.monitor.dashboard.http.server.HTTPServer")
    def test_main_opens_browser(self, mock_server_class):
        from sentinel.monitor.dashboard import main

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        with patch("webbrowser.open") as mock_web:
            result = main(["--open", "--trace-dir", "/tmp"])
            self.assertEqual(result, 0)
            mock_web.assert_called_once_with("http://localhost:8080")
