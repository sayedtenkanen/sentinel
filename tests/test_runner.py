"""Unit tests for the CLI runner."""

import contextlib
import io
import json
import os
import tempfile
import unittest

from sentinel.deploy.runner import create_parser, main


class TestRunnerParser(unittest.TestCase):
    def test_parser_creates(self):
        parser = create_parser()
        self.assertIsNotNone(parser)
        args = parser.parse_args(["file.py"])
        self.assertEqual(args.paths, ["file.py"])

    def test_parser_default_format(self):
        parser = create_parser()
        args = parser.parse_args(["some_file.py"])
        self.assertEqual(args.format, "markdown")

    def test_parser_json_format(self):
        parser = create_parser()
        args = parser.parse_args(["f.py", "--format", "json"])
        self.assertEqual(args.format, "json")

    def test_parser_disable_agent(self):
        parser = create_parser()
        args = parser.parse_args(["f.py", "--disable-agent", "security"])
        self.assertIn("security", args.disable_agent)

    def test_parser_output_file(self):
        parser = create_parser()
        args = parser.parse_args(["f.py", "-o", "report.md"])
        self.assertEqual(args.output, "report.md")

    def test_parser_trace_dir(self):
        parser = create_parser()
        args = parser.parse_args(["f.py", "--trace-dir", "./traces"])
        self.assertEqual(args.trace_dir, "./traces")

    def test_parser_verbose(self):
        parser = create_parser()
        args = parser.parse_args(["f.py", "-v"])
        self.assertTrue(args.verbose)


class TestRunnerMain(unittest.TestCase):
    def test_main_with_nonexistent_file(self):
        exit_code = main(["nonexistent_file_12345.py"])
        self.assertEqual(exit_code, 1)

    def test_main_with_existing_file_markdown(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            path = f.name
        try:
            exit_code = main([path])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_with_existing_file_json(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            path = f.name
        try:
            exit_code = main([path, "--format", "json"])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_output_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            src = f.name
        out_path = src + ".out.md"
        try:
            exit_code = main([src, "-o", out_path])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path) as f:
                content = f.read()
            self.assertIn("Code Review Report", content)
        finally:
            os.unlink(src)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_main_json_output_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            src = f.name
        out_path = src + ".out.json"
        try:
            exit_code = main([src, "--format", "json", "-o", out_path])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path) as f:
                data = json.load(f)
            self.assertIn("score", data)
        finally:
            os.unlink(src)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_main_with_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "a.py")
            f2 = os.path.join(tmpdir, "b.py")
            with open(f1, "w") as f:
                f.write("x = 1\n")
            with open(f2, "w") as f:
                f.write("y = 2\n")
            exit_code = main([tmpdir, "--format", "json"])
            self.assertEqual(exit_code, 0)

    def test_main_with_disable_agent(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            path = f.name
        try:
            exit_code = main([path, "--disable-agent", "security"])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_with_trace_dir(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            src = f.name
        with tempfile.TemporaryDirectory() as trace_dir:
            try:
                exit_code = main([src, "--trace-dir", trace_dir])
                self.assertEqual(exit_code, 0)
                files = os.listdir(trace_dir)
                self.assertGreater(len(files), 0)
            finally:
                os.unlink(src)

    def test_main_with_verbose(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            path = f.name
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                exit_code = main([path, "-v"])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_verbose_with_output_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            src = f.name
        out_path = src + ".out.md"
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                exit_code = main([src, "-v", "-o", out_path])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out_path))
        finally:
            os.unlink(src)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_main_verbose_with_trace_dir(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            src = f.name
        with tempfile.TemporaryDirectory() as trace_dir:
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    exit_code = main([src, "-v", "--trace-dir", trace_dir])
                self.assertEqual(exit_code, 0)
                self.assertGreater(len(os.listdir(trace_dir)), 0)
            finally:
                os.unlink(src)

    def test_main_with_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                contextlib.redirect_stderr(io.StringIO()),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = main(
                    [
                        "--feedback",
                        "finding123",
                        "trace_001.json",
                        "--rating",
                        "correct",
                        "--comment",
                        "Looks good",
                        "--trace-dir",
                        tmpdir,
                    ]
                )
            self.assertEqual(exit_code, 0)
            feedback_files = [f for f in os.listdir(tmpdir) if f.startswith("feedback_")]
            self.assertGreater(len(feedback_files), 0)


if __name__ == "__main__":
    unittest.main()
