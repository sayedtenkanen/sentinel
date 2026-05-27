"""Unit tests for tools/ ast_tools, git_tools, and config."""

import os
import tempfile
import unittest

from sentinel.core.types import Finding, Severity
from sentinel.tools.ast_tools import (
    compute_complexity,
    find_function_lengths,
    find_unused_imports,
)
from sentinel.tools.config import (
    agent_config,
    filter_files,
    find_config,
    load_config,
    matches_exclude,
    matches_suppress,
    suppress_findings,
)
from sentinel.tools.git_tools import detect_language, parse_diff


class TestComputeComplexity(unittest.TestCase):
    def test_simple_code(self):
        source = "x = 1\ny = 2\n"
        complexity, nesting = compute_complexity(source)
        self.assertEqual(complexity, 1)
        self.assertEqual(nesting, 0)

    def test_if_statement(self):
        source = "if x:\n    pass\n"
        complexity, nesting = compute_complexity(source)
        self.assertGreaterEqual(complexity, 2)
        self.assertGreaterEqual(nesting, 1)

    def test_nested_conditionals(self):
        source = """if a:
    if b:
        if c:
            pass
"""
        complexity, nesting = compute_complexity(source)
        self.assertGreaterEqual(complexity, 4)
        self.assertGreaterEqual(nesting, 3)

    def test_syntax_error_returns_zero(self):
        complexity, nesting = compute_complexity("if True\n")
        self.assertEqual(complexity, 0)
        self.assertEqual(nesting, 0)


class TestFindFunctionLengths(unittest.TestCase):
    def test_function_length(self):
        source = """def foo():
    x = 1
    y = 2
    z = 3
"""
        funcs = find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0]["name"], "foo")
        self.assertEqual(funcs[0]["length"], 4)

    def test_async_function(self):
        source = """async def bar():
    pass
"""
        funcs = find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0]["name"], "bar")


class TestFindUnusedImports(unittest.TestCase):
    def test_unused_import(self):
        source = """import json

data = json.loads('{}')
"""
        unused = find_unused_imports(source)
        names = {u["name"] for u in unused}
        self.assertNotIn("json", names)

    def test_used_import_not_reported(self):
        source = """import os
os.getcwd()
"""
        unused = find_unused_imports(source)
        names = {u["name"] for u in unused}
        self.assertNotIn("os", names)

    def test_from_import(self):
        source = """from typing import Optional, List

x = 1
"""
        unused = find_unused_imports(source)
        names = {u["name"] for u in unused}
        self.assertIn("typing.Optional", names)
        self.assertIn("typing.List", names)


class TestDetectLanguage(unittest.TestCase):
    def test_python(self):
        self.assertEqual(detect_language("file.py"), "python")

    def test_javascript(self):
        self.assertEqual(detect_language("file.js"), "javascript")

    def test_unknown(self):
        self.assertEqual(detect_language("file.xyz"), "")

    def test_case_insensitive(self):
        self.assertEqual(detect_language("File.PY"), "python")


class TestParseDiff(unittest.TestCase):
    def test_parse_simple_diff(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
-old line
+new line
"""
        files = parse_diff(diff)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["path"], "test.py")
        self.assertIn("new line", files[0]["added"])
        self.assertIn("old line", files[0]["removed"])

    def test_empty_diff(self):
        files = parse_diff("")
        self.assertEqual(len(files), 0)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_config = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp_config.write(
            '{"exclude": ["tests/"], "suppress": [{"rule": "SEC*", "pattern": "**/context.py"}], "agents": {"style": {"max_line_length": 80}}, "output": {"verbose": true}}'
        )
        self.tmp_config.close()

    def tearDown(self):
        os.unlink(self.tmp_config.name)

    def test_load_config_reads_file(self):
        cfg = load_config(self.tmp_config.name)
        self.assertEqual(cfg["exclude"], ["tests/"])
        self.assertEqual(len(cfg["suppress"]), 1)
        self.assertEqual(cfg["suppress"][0]["rule"], "SEC*")

    def test_load_config_not_found(self):
        cfg = load_config("/nonexistent/.code-review.json")
        self.assertEqual(cfg, {"exclude": [], "agents": {}, "output": {}})

    def test_load_config_no_path_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            prev = os.getcwd()
            os.chdir(d)
            try:
                cfg = load_config()
                self.assertIn("exclude", cfg)
            finally:
                os.chdir(prev)

    def test_find_config_found(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, ".code-review.json")
            with open(cfg_path, "w") as f:
                f.write("{}")
            result = find_config(d)
            self.assertEqual(result, os.path.realpath(cfg_path))

    def test_find_config_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            result = find_config(d)
            self.assertIsNone(result)

    def test_matches_exclude_fnmatch(self):
        self.assertTrue(matches_exclude("foo/bar/baz.py", ["*.py"]))
        self.assertTrue(matches_exclude("foo/bar/test.py", ["**/test.py"]))
        self.assertFalse(matches_exclude("foo/bar/readme.md", ["*.py"]))

    def test_matches_exclude_trailing_slash(self):
        self.assertTrue(matches_exclude("tests/test_foo.py", ["tests/"]))
        self.assertTrue(matches_exclude("tests/bar/test_baz.py", ["tests/"]))
        self.assertTrue(matches_exclude("src/tests.py", ["tests/"]))

    def test_matches_exclude_substring(self):
        self.assertTrue(matches_exclude("/home/user/project/_assets/secrets.txt", ["_assets"]))

    def test_filter_files_empty_patterns(self):
        files = [("a.py", ""), ("b.py", "")]
        result = filter_files(files, {"exclude": []})
        self.assertEqual(len(result), 2)

    def test_filter_files_excludes(self):
        files = [("a.py", ""), ("tests/test_a.py", ""), ("b.py", "")]
        result = filter_files(files, {"exclude": ["tests/"]})
        self.assertEqual(len(result), 2)
        paths = [p for p, _ in result]
        self.assertNotIn("tests/test_a.py", paths)

    def test_agent_config(self):
        cfg = {"agents": {"style": {"max_line_length": 80}}}
        self.assertEqual(agent_config(cfg, "style"), {"max_line_length": 80})
        self.assertEqual(agent_config(cfg, "security"), {})

    def test_matches_suppress_rule_match(self):
        f = Finding(rule_id="SEC003", file="foo/context.py", severity=Severity.CRITICAL)
        self.assertTrue(matches_suppress(f, {"rule": "SEC003", "pattern": "**/context.py"}))
        self.assertFalse(matches_suppress(f, {"rule": "SEC004", "pattern": "**/context.py"}))

    def test_matches_suppress_wildcard_rule(self):
        f = Finding(rule_id="SEC003", file="foo/context.py", severity=Severity.CRITICAL)
        self.assertTrue(matches_suppress(f, {"rule": "*", "pattern": "**/context.py"}))

    def test_matches_suppress_wildcard_pattern(self):
        f = Finding(rule_id="SEC003", file="foo/context.py", severity=Severity.CRITICAL)
        self.assertTrue(matches_suppress(f, {"rule": "SEC003", "pattern": "*"}))

    def test_matches_suppress_no_match(self):
        f = Finding(rule_id="SEC003", file="bar/other.py", severity=Severity.CRITICAL)
        self.assertFalse(matches_suppress(f, {"rule": "SEC003", "pattern": "**/context.py"}))

    def test_suppress_findings_removes_matches(self):
        f1 = Finding(rule_id="SEC003", file="ctx/context.py", severity=Severity.CRITICAL)
        f2 = Finding(rule_id="SEC004", file="ctx/context.py", severity=Severity.CRITICAL)
        f3 = Finding(rule_id="STY001", file="style.py", severity=Severity.INFO)
        config = {"suppress": [{"rule": "SEC*", "pattern": "**/context.py"}]}
        result = suppress_findings([f1, f2, f3], config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule_id, "STY001")

    def test_suppress_findings_no_rules(self):
        f = Finding(rule_id="SEC003", file="x.py", severity=Severity.CRITICAL)
        result = suppress_findings([f], {})
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
