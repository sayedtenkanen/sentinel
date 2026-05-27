"""Unit tests for all 5 sub-agents."""

import unittest

from sentinel.agents.best_practices import BestPracticesAgent
from sentinel.agents.documentation import DocumentationAgent
from sentinel.agents.security import SecurityAgent
from sentinel.agents.static_analysis import StaticAnalysisAgent
from sentinel.agents.style import StyleAgent
from sentinel.agents.summary import SummaryAgent
from sentinel.core.types import FileContext, Severity


def make_file(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content)


class TestStaticAnalysisAgent(unittest.TestCase):
    def setUp(self):
        self.agent = StaticAnalysisAgent()

    def test_line_too_long(self):
        content = "x = " + "a" * 200
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST001", rule_ids)

    def test_complex_code(self):
        content = """def foo(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z):
    if a:
        pass
    if b:
        pass
    if c:
        pass
    if d:
        pass
    if e:
        pass
    if f:
        pass
    if g:
        pass
    if h:
        pass
    if i:
        pass
    if j:
        pass
    if k:
        pass
    if l:
        pass
    if m:
        pass
    if n:
        pass
    if o:
        pass
    if p:
        pass
    if q:
        pass
    if r:
        pass
    if s:
        pass
    if t:
        pass
    if u:
        pass
    if v:
        pass
    if w:
        pass
    if x:
        pass
    if y:
        pass
    if z:
        pass
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST002", rule_ids)

    def test_long_function(self):
        content = "def foo():\n" + "    pass\n" * 60
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST003", rule_ids)

    def test_deep_nesting(self):
        content = """def foo(a, b, c, d, e, f, g):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                pass
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST004", rule_ids)

    def test_unused_import(self):
        content = """import os
import sys

x = 1
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST005", rule_ids)

    def test_trailing_whitespace(self):
        content = "x = 1  \n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST006", rule_ids)

    def test_clean_code_no_findings(self):
        content = """x = 1
y = 2
"""
        findings = self.agent.analyze(make_file(content))
        self.assertEqual(len(findings), 0)

    def test_too_many_params(self):
        content = "def foo(a, b, c, d, e, f, g, h, i): pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST008", rule_ids)

    def test_shadow_builtin(self):
        content = "def list(): pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("ST009", rule_ids)

    def test_non_python_file(self):
        content = "function foo() { return 1; }"
        file = make_file(content, path="test.js")
        findings = self.agent.analyze(file)
        self.assertEqual(len(findings), 0)


class TestSecurityAgent(unittest.TestCase):
    def setUp(self):
        self.agent = SecurityAgent()

    def test_hardcoded_password(self):
        findings = self.agent.analyze(make_file('password = "secret123"'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC001", rule_ids)

    def test_hardcoded_api_key(self):
        findings = self.agent.analyze(make_file('api_key = "sk-1234567890abcdef"'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC002", rule_ids)

    def test_eval_detected(self):
        findings = self.agent.analyze(make_file('eval("x")'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC003", rule_ids)

    def test_exec_detected(self):
        findings = self.agent.analyze(make_file('exec("x")'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC004", rule_ids)

    def test_pickle_detected(self):
        findings = self.agent.analyze(make_file("pickle.loads(data)"))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC005", rule_ids)

    def test_shell_injection(self):
        findings = self.agent.analyze(make_file('subprocess.call("ls", shell=True)'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC006", rule_ids)

    def test_os_system(self):
        findings = self.agent.analyze(make_file('os.system("ls")'))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC007", rule_ids)

    def test_weak_hash(self):
        findings = self.agent.analyze(make_file("hashlib.md5(data)"))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC019", rule_ids)

    def test_ssl_verify_false(self):
        findings = self.agent.analyze(make_file("requests.get(url, verify=False)"))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC018", rule_ids)

    def test_clean_code_no_findings(self):
        findings = self.agent.analyze(make_file("x = 1\nprint(x)\n"))
        self.assertEqual(len(findings), 0)


class TestStyleAgent(unittest.TestCase):
    def setUp(self):
        self.agent = StyleAgent()

    def test_class_name_not_capwords(self):
        findings = self.agent.analyze(make_file("class bad_name: pass"))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY002", rule_ids)

    def test_function_name_not_snake_case(self):
        findings = self.agent.analyze(make_file("def BadName(): pass"))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY003", rule_ids)

    def test_missing_docstring_on_function(self):
        content = "def foo():\n    pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY004", rule_ids)

    def test_magic_number(self):
        content = "x = 86400\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY006", rule_ids)

    def test_is_comparison(self):
        content = "if x == None:\n    pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY007", rule_ids)

    def test_import_order_violation(self):
        content = """import os
import requests
import sys
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY001", rule_ids)

    def test_clean_function_with_docstring(self):
        content = 'def foo():\n    """Do something."""\n    pass\n'
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertNotIn("STY004", rule_ids)

    def test_non_python_file(self):
        file = make_file("function foo() {}", path="test.js")
        findings = self.agent.analyze(file)
        self.assertEqual(len(findings), 0)

    def test_unnecessary_else(self):
        content = """def foo(x):
    if x:
        return 1
    else:
        return 2
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("STY008", rule_ids)


class TestBestPracticesAgent(unittest.TestCase):
    def setUp(self):
        self.agent = BestPracticesAgent()

    def test_bare_except(self):
        content = """try:
    x = 1
except:
    pass
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP001", rule_ids)

    def test_lambda_assignment(self):
        content = "f = lambda x: x * 2\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP002", rule_ids)

    def test_mutable_default(self):
        content = "def foo(items=[]):\n    pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP003", rule_ids)

    def test_global_var(self):
        content = """x = 1
def foo():
    global x
    x = 2
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP004", rule_ids)

    def test_missing_context_manager(self):
        content = 'f = open("test.txt")\n'
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP007", rule_ids)

    def test_type_comparison(self):
        content = "type(x) == int\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP008", rule_ids)

    def test_dict_keys_iteration(self):
        content = "for k in d.keys():\n    pass\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("BP009", rule_ids)

    def test_clean_function(self):
        content = (
            "def foo(items: list = None) -> list:\n"
            '    """Do work."""\n'
            "    if items is None:\n"
            "        items = []\n"
            "    return items\n"
        )
        findings = self.agent.analyze(make_file(content))
        bp_ids = {f.rule_id for f in findings if f.rule_id.startswith("BP")}
        self.assertNotIn("BP003", bp_ids)
        self.assertNotIn("BP004", bp_ids)
        self.assertNotIn("BP007", bp_ids)

    def test_non_python_file(self):
        file = make_file("function foo() {}", path="test.js")
        findings = self.agent.analyze(file)
        self.assertEqual(len(findings), 0)


class TestDocumentationAgent(unittest.TestCase):
    def setUp(self):
        self.agent = DocumentationAgent()

    def test_redundant_comment(self):
        content = "# increment counter by one\ncounter += 1\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("DOC002", rule_ids)

    def test_stale_comment(self):
        content = "# HACK: legacy workaround for old API\nx = 1\n"
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("DOC003", rule_ids)

    def test_todo_density(self):
        content = (
            "# TODO: fix this\n# TODO: refactor\n# FIXME: bug\n# HACK: workaround\nx = 1\n" * 5
        )
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("DOC004", rule_ids)

    def test_undocumented_params(self):
        content = """def foo(a, b):
    \"\"\"Do something.\"\"\"
    return a + b
"""
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("DOC005", rule_ids)

    def test_module_docstring_missing_on_large_file(self):
        content = "x = 1\n" * 30
        findings = self.agent.analyze(make_file(content))
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("DOC001", rule_ids)

    def test_empty_file(self):
        findings = self.agent.analyze(make_file(""))
        self.assertEqual(len(findings), 0)

    def _test_empty_function_body(self):
        content = "def foo():\n    pass\n"
        findings = self.agent.analyze(make_file(content))
        # Should not crash
        self.assertIsInstance(findings, list)


class TestSummaryAgent(unittest.TestCase):
    def setUp(self):
        self.agent = SummaryAgent()

    def test_summarize_empty_report(self):
        from sentinel.core.types import ReviewReport

        report = ReviewReport()
        summary = self.agent.summarize(report)
        self.assertIn("Score: 100/100", summary)
        self.assertIn("Excellent", summary)

    def test_summarize_with_findings(self):
        from sentinel.core.types import AgentResult, AgentStatus, Finding, ReviewReport

        report = ReviewReport()
        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            findings=[
                Finding(severity=Severity.CRITICAL, message="bad"),
                Finding(severity=Severity.HIGH, message="worse"),
            ],
        )
        report.agent_results.append(result)
        summary = self.agent.summarize(report)
        self.assertIn("Critical: 1", summary)
        self.assertIn("High: 1", summary)


if __name__ == "__main__":
    unittest.main()
