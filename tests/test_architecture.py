"""Unit tests for the architecture agent."""

import unittest

from sentinel.agents.architecture import ArchitectureAgent
from sentinel.core.types import FileContext


def make_file(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content)


class TestArchitectureAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ArchitectureAgent()

    def test_no_findings_on_empty_file(self):
        findings = self.agent.analyze(make_file("", "empty.py"))
        self.assertEqual(len(findings), 0)

    def test_no_findings_on_simple_file(self):
        findings = self.agent.analyze(make_file("x = 1\n", "simple.py"))
        self.assertEqual(len(findings), 0)

    def test_no_cycle_one_file(self):
        f = self.agent.analyze(make_file("x = 1\n", "app.py"))
        self.assertEqual(len(f), 0)

    def test_cycle_detected_across_files(self):
        self.agent.analyze(make_file("import b\n", "a.py"))
        findings = self.agent.analyze(make_file("import a\n", "b.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertIn("ARC001", arc_ids)

    def test_god_module_detected(self):
        agent = ArchitectureAgent(god_module_threshold=3)
        deps = ", ".join(f"lib{i}" for i in range(5))
        source = f"import {deps.replace(', ', ',')}\n"
        findings = agent.analyze(make_file(source, "god.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertIn("ARC002", arc_ids)

    def test_god_module_below_threshold(self):
        agent = ArchitectureAgent(god_module_threshold=20)
        findings = agent.analyze(make_file("import os\n", "small.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertNotIn("ARC002", arc_ids)

    def test_isolated_module_detected(self):
        self.agent.analyze(make_file("import os\n", "a.py"))
        findings = self.agent.analyze(make_file("x = 1\n", "isolated.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertIn("ARC003", arc_ids)

    def test_no_isolated_single_module(self):
        findings = self.agent.analyze(make_file("x = 1\n", "only.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertNotIn("ARC003", arc_ids)

    def test_leaf_module_detected(self):
        self.agent.analyze(make_file("from core import utils\n", "a.py"))
        findings = self.agent.analyze(make_file("import os\n", "leaf.py"))
        arc_ids = {f.rule_id for f in findings}
        self.assertIn("ARC004", arc_ids)

    def test_summary(self):
        self.agent.analyze(make_file("import os\n", "main.py"))
        self.agent.analyze(make_file("", "utils.py"))
        summary = self.agent.summary()
        self.assertIn("modules", summary)
        self.assertIn("cycles", summary)
        self.assertIn("god modules", summary)

    def test_disabled_agent(self):
        agent = ArchitectureAgent(enabled=False)
        findings = agent.analyze(make_file("x = 1\n"))
        self.assertEqual(len(findings), 0)

    def test_config_schema(self):
        schema = self.agent.get_config_schema()
        self.assertIn("god_module_threshold", schema)
        self.assertEqual(schema["god_module_threshold"]["type"], "integer")

    def test_agent_name(self):
        self.assertEqual(self.agent.name, "architecture")


if __name__ == "__main__":
    unittest.main()
