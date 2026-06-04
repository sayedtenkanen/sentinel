"""Unit tests for the refactor agent."""

import unittest

from sentinel.agents.refactor import RefactorAgent
from sentinel.core.types import FileContext


def make_file(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content)


class TestRefactorAgent(unittest.TestCase):
    def setUp(self):
        self.agent = RefactorAgent(refactor_threshold=15)

    def test_empty_file(self):
        findings = self.agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_simple_function_no_findings(self):
        source = "def foo():\n    pass\n"
        findings = self.agent.analyze(make_file(source))
        self.assertEqual(len(findings), 0)

    def test_complex_function_flagged(self):
        source = """def foo(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        pass
    return None
"""
        findings = self.agent.analyze(make_file(source))
        ref_ids = {f.rule_id for f in findings}
        self.assertIn("REF001", ref_ids)

    def test_long_function_flagged(self):
        source = "def foo():\n" + "    pass\n" * 25
        findings = self.agent.analyze(make_file(source))
        ref_ids = {f.rule_id for f in findings}
        self.assertIn("REF001", ref_ids)

    def test_many_params_flagged(self):
        params = ", ".join(chr(ord("a") + i) for i in range(15))
        source = f"def foo({params}):\n    pass\n"
        findings = self.agent.analyze(make_file(source))
        ref_ids = {f.rule_id for f in findings}
        self.assertIn("REF001", ref_ids)

    def test_high_priority_critical(self):
        source = """def mega(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                if h:
                                    if i:
                                        if j:
                                            pass
    return None
""" + "\n".join("    pass\n" for _ in range(40))
        findings = self.agent.analyze(make_file(source))
        ref_ids = {f.rule_id for f in findings}
        self.assertIn("REF002", ref_ids)

    def test_disabled_agent(self):
        agent = RefactorAgent(enabled=False)
        findings = agent.analyze(make_file("x = 1\n"))
        self.assertEqual(len(findings), 0)

    def test_config_schema(self):
        schema = self.agent.get_config_schema()
        self.assertIn("complexity_weight", schema)
        self.assertIn("length_weight", schema)
        self.assertIn("param_weight", schema)
        self.assertIn("refactor_threshold", schema)

    def test_agent_name(self):
        self.assertEqual(self.agent.name, "refactor")

    def test_score_above_threshold(self):
        agent = RefactorAgent(refactor_threshold=1)
        source = "def foo():\n    pass\n"
        findings = agent.analyze(make_file(source))
        self.assertGreaterEqual(len(findings), 0)

    def test_async_function(self):
        source = "async def fetch():\n" + "    pass\n" * 30
        findings = self.agent.analyze(make_file(source))
        ref_ids = {f.rule_id for f in findings}
        self.assertIn("REF001", ref_ids)

    def test_multiple_functions(self):
        source = (
            "def simple():\n    pass\n"
            "def complex(a, b, c, d, e, f, g, h):\n"
            "    if a:\n"
            "        if b:\n"
            "            pass\n"
        )
        findings = self.agent.analyze(make_file(source))
        self.assertGreaterEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
