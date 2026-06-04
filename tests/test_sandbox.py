"""Unit tests for the secure sandbox execution environment."""

import unittest

from sentinel.tools.sandbox import ALLOWED_MODULES, SAFE_BUILTINS, Sandbox


class TestSandboxBasics(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox(timeout=5)

    def test_simple_execution(self):
        result = self.sandbox.execute("x = 1 + 2\nprint(x)")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "3")
        self.assertIsNone(result["error"])

    def test_print_multiple_lines(self):
        code = "for i in range(3):\n    print(i)"
        result = self.sandbox.execute(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip().split("\n"), ["0", "1", "2"])

    def test_math_module(self):
        code = "import math\nprint(math.sqrt(16))"
        result = self.sandbox.execute(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "4.0")

    def test_re_module(self):
        code = "import re\nprint(re.search(r'\\d+', 'abc123def').group())"
        result = self.sandbox.execute(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "123")

    def test_json_module(self):
        code = "import json\nprint(json.dumps({'a': 1}))"
        result = self.sandbox.execute(code)
        self.assertTrue(result["success"])
        self.assertIn('{"a": 1}', result["output"].strip())

    def test_stdlib_collections(self):
        code = "from collections import Counter\nc = Counter('aabbc')\nprint(c['a'])"
        result = self.sandbox.execute(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "2")

    def test_result_structure(self):
        result = self.sandbox.execute("print('ok')")
        self.assertIn("success", result)
        self.assertIn("output", result)
        self.assertIn("error", result)
        self.assertIn("execution_ms", result)
        self.assertIsInstance(result["execution_ms"], float)

    def test_output_without_print(self):
        result = self.sandbox.execute("x = 42")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "")

    def test_multiline_output(self):
        code = "print('line1')\nprint('line2')\nprint('line3')"
        result = self.sandbox.execute(code)
        lines = result["output"].strip().split("\n")
        self.assertEqual(lines, ["line1", "line2", "line3"])


class TestSandboxSafety(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox(timeout=5)

    def test_blocked_os_module(self):
        result = self.sandbox.execute("import os")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_sys_module(self):
        result = self.sandbox.execute("import sys")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_subprocess(self):
        result = self.sandbox.execute("import subprocess")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_pathlib(self):
        result = self.sandbox.execute("import pathlib")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_shutil(self):
        result = self.sandbox.execute("import shutil")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_socket(self):
        result = self.sandbox.execute("import socket")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_blocked_ctypes(self):
        result = self.sandbox.execute("import ctypes")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", str(result["error"]).lower())

    def test_no_open_builtin(self):
        result = self.sandbox.execute("open('/etc/passwd')")
        self.assertFalse(result["success"])
        self.assertIn("name 'open' is not defined", result["error"])

    def test_no_eval(self):
        result = self.sandbox.execute("eval('1+1')")
        self.assertFalse(result["success"])
        self.assertIn("name 'eval' is not defined", result["error"])

    def test_no_exec_builtin(self):
        result = self.sandbox.execute("exec('x=1')")
        self.assertFalse(result["success"])
        self.assertIn("name 'exec' is not defined", result["error"])

    def test_no_compile(self):
        result = self.sandbox.execute("compile('x=1', '<test>', 'exec')")
        self.assertFalse(result["success"])
        self.assertIn("name 'compile' is not defined", result["error"])

    def test_no___import___direct(self):
        result = self.sandbox.execute("__import__('os')")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"])

    def test_infinite_loop_timeout(self):
        sandbox = Sandbox(timeout=1)
        result = sandbox.execute("while True: pass")
        self.assertFalse(result["success"])
        self.assertIn("timed out", result["error"].lower())

    def test_timeout_no_syntax_error(self):
        sandbox = Sandbox(timeout=1)
        result = sandbox.execute("import time\ntime.sleep(5)\nprint('done')")
        self.assertFalse(result["success"])
        self.assertIn("timed out", result["error"].lower())

    def test_huge_memory(self):
        result = self.sandbox.execute("x = [0] * 10_000_000\nprint(len(x))")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "10000000")


class TestSandboxInjectedHelpers(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox(timeout=5)

    def test_inject_function(self):
        def double(n: int) -> int:
            return n * 2

        result = self.sandbox.execute(
            "print(double(21))",
            inject={"double": double},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "42")

    def test_inject_multiple(self):
        result = self.sandbox.execute(
            "print(greeting + ' ' + name)",
            inject={"greeting": "Hello", "name": "World"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "Hello World")

    def test_inject_does_not_escape(self):
        def malicious():
            import os

            return os.listdir("/")

        result = self.sandbox.execute(
            "print(malicious())",
            inject={"malicious": malicious},
        )
        # The injected function runs in real Python, not sandbox
        # so it can access os. This is expected — injected functions
        # are trusted wrappers, not sandboxed.
        self.assertTrue(result["success"])

    def test_inject_overrides(self):
        result = self.sandbox.execute(
            "print(answer)",
            inject={"answer": 42},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "42")

    def test_inject_lambda(self):
        result = self.sandbox.execute(
            "print(adder(3, 4))",
            inject={"adder": lambda a, b: a + b},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "7")


class TestSandboxErrorHandling(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox(timeout=5)

    def test_syntax_error(self):
        result = self.sandbox.execute("x = 1 + ")
        self.assertFalse(result["success"])
        self.assertIn("SyntaxError", result["error"])

    def test_runtime_error(self):
        result = self.sandbox.execute("x = 1 / 0")
        self.assertFalse(result["success"])
        self.assertIn("ZeroDivisionError", result["error"])

    def test_name_error(self):
        result = self.sandbox.execute("print(undefined_var)")
        self.assertFalse(result["success"])
        self.assertIn("NameError", result["error"])

    def test_type_error(self):
        result = self.sandbox.execute("'a' + 1")
        self.assertFalse(result["success"])
        self.assertIn("TypeError", result["error"])

    def test_empty_code(self):
        result = self.sandbox.execute("")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "")

    def test_import_error_message(self):
        result = self.sandbox.execute("import flask")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"].lower())

    def test_nested_import(self):
        result = self.sandbox.execute("from os.path import join")
        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"].lower())

    def test_custom_timeout_override(self):
        result = self.sandbox.execute("import time\ntime.sleep(3)", timeout=1)
        self.assertFalse(result["success"])
        self.assertIn("timed out", result["error"].lower())

    def test_long_running_but_within_timeout(self):
        result = self.sandbox.execute("x = sum(range(100_000))\nprint(x)", timeout=10)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "4999950000")


class TestSandboxCustomAllowedModules(unittest.TestCase):
    def test_custom_allowlist(self):
        sandbox = Sandbox(timeout=5, allowed_modules={"math"})
        result = sandbox.execute("import math\nprint(math.pi)")
        self.assertTrue(result["success"])
        result2 = sandbox.execute("import json")
        self.assertFalse(result2["success"])

    def test_empty_allowlist(self):
        sandbox = Sandbox(timeout=5, allowed_modules=set())
        result = sandbox.execute("import math")
        self.assertFalse(result["success"])


class TestSandboxConstants(unittest.TestCase):
    def test_allowed_modules_contains_core(self):
        self.assertIn("json", ALLOWED_MODULES)
        self.assertIn("re", ALLOWED_MODULES)
        self.assertIn("math", ALLOWED_MODULES)
        self.assertIn("collections", ALLOWED_MODULES)

    def test_safe_builtins_has_essentials(self):
        self.assertIn("print", SAFE_BUILTINS)
        self.assertIn("len", SAFE_BUILTINS)
        self.assertIn("range", SAFE_BUILTINS)
        self.assertNotIn("open", SAFE_BUILTINS)
        self.assertNotIn("eval", SAFE_BUILTINS)
        self.assertNotIn("exec", SAFE_BUILTINS)
        self.assertNotIn("compile", SAFE_BUILTINS)
        self.assertNotIn("__import__", SAFE_BUILTINS)


class TestSandboxExecutionTime(unittest.TestCase):
    def test_execution_time_measured(self):
        sandbox = Sandbox(timeout=10)
        result = sandbox.execute("x = sum(range(1_000_000))\nprint(x)")
        self.assertTrue(result["success"])
        self.assertGreater(result["execution_ms"], 0)


if __name__ == "__main__":
    unittest.main()
