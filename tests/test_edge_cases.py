"""Edge case tests to fill coverage gaps."""

import unittest

from sentinel.agents.best_practices import BestPracticesAgent
from sentinel.agents.documentation import DocumentationAgent
from sentinel.agents.security import SecurityAgent
from sentinel.agents.static_analysis import StaticAnalysisAgent
from sentinel.agents.style import StyleAgent
from sentinel.core.types import FileContext, Finding, Severity
from sentinel.reporting.report import format_finding


def make_file(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content)


class TestEdgeCaseEmptyFiles(unittest.TestCase):
    def test_empty_string_static_analysis(self):
        agent = StaticAnalysisAgent()
        findings = agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_empty_string_security(self):
        agent = SecurityAgent()
        findings = agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_empty_string_style(self):
        agent = StyleAgent()
        findings = agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_empty_string_best_practices(self):
        agent = BestPracticesAgent()
        findings = agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_empty_string_documentation(self):
        agent = DocumentationAgent()
        findings = agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def test_syntax_error_code(self):
        agent = StaticAnalysisAgent()
        findings = agent.analyze(make_file("def foo(:"))
        # Should not crash
        self.assertIsInstance(findings, list)


class TestEdgeCaseFinding(unittest.TestCase):
    def test_finding_code_snippet_long(self):
        f = Finding(
            agent_name="test",
            severity=Severity.CRITICAL,
            message="test",
            code_snippet="x" * 100,
        )
        formatted = format_finding(f)
        self.assertIn("test", formatted)

    def test_finding_with_column(self):
        f = Finding(
            agent_name="test",
            severity=Severity.HIGH,
            message="msg",
            file="test.py",
            line=10,
            column=5,
        )
        formatted = format_finding(f)
        self.assertIn("test.py:10:5", formatted)


class TestEdgeCaseDisabledAgent(unittest.TestCase):
    def test_disabled_agent_no_error(self):
        agent = StaticAnalysisAgent(enabled=False)
        file = make_file('password = "secret"')
        result = agent.run(file)
        self.assertEqual(len(result.findings), 0)
        self.assertIsNone(result.error)


class TestEdgeCaseCodeFindings(unittest.TestCase):
    def test_warning_comments(self):
        agent = DocumentationAgent()
        content = "# increment counter by one\nx += 1\n"
        findings = agent.analyze(make_file(content))
        self.assertGreater(len(findings), 0)

    def test_ssl_verify_pattern(self):
        agent = SecurityAgent()
        content = 'requests.get("https://example.com", verify=False)'
        findings = agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC018", rule_ids)


class TestEdgeCaseTypes(unittest.TestCase):
    def test_review_scope_values(self):
        from sentinel.core.types import ReviewScope

        self.assertEqual(ReviewScope.FULL_FILE.value, "full_file")
        self.assertEqual(ReviewScope.DIFF.value, "diff")
        self.assertEqual(ReviewScope.PR.value, "pr")

    def test_agent_status_values(self):
        from sentinel.core.types import AgentStatus

        self.assertEqual(AgentStatus.PENDING.value, "pending")
        self.assertEqual(AgentStatus.RUNNING.value, "running")
        self.assertEqual(AgentStatus.COMPLETED.value, "completed")
        self.assertEqual(AgentStatus.FAILED.value, "failed")

    def test_finding_category_default(self):
        f = Finding()
        self.assertEqual(f.category, "")


if __name__ == "__main__":
    unittest.main()
