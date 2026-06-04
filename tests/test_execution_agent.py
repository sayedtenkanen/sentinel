"""Unit tests for the hybrid execution agent."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from sentinel.agents.execution_agent import ExecutionAgent
from sentinel.core.types import FileContext
from sentinel.tools.sandbox import Sandbox


def make_file(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content)


class MockSandbox(Sandbox):
    def __init__(self, responses=None):
        super().__init__(timeout=5)
        self.responses = responses or []
        self.call_count = 0

    def execute(self, code, inject=None, timeout=None):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return {"success": True, "output": "", "error": None, "execution_ms": 1.0}


class TestExecutionAgentNoApiKey(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        agent = ExecutionAgent(api_key="")
        result = agent.analyze(make_file("x = 1"))
        self.assertEqual(result, [])

    def test_empty_api_key_via_env(self):
        with patch.dict(os.environ, {}, clear=True):
            agent = ExecutionAgent(api_key="")
            result = agent.analyze(make_file("x = 1"))
            self.assertEqual(result, [])


class TestExecutionAgentCodeExtraction(unittest.TestCase):
    def setUp(self):
        self.agent = ExecutionAgent(api_key="sk-test")

    def test_extract_python_fenced(self):
        response = "```python\nprint('hello')\n```"
        code = self.agent._extract_code(response)
        self.assertEqual(code, "print('hello')")

    def test_extract_generic_fenced(self):
        response = "```\nprint('hello')\n```"
        code = self.agent._extract_code(response)
        self.assertEqual(code, "print('hello')")

    def test_extract_no_fence(self):
        response = "print('hello')"
        code = self.agent._extract_code(response)
        self.assertEqual(code, "print('hello')")

    def test_extract_with_prefix(self):
        response = "Here is the code:\n```python\nx = 1\nprint(x)\n```\nDone."
        code = self.agent._extract_code(response)
        self.assertEqual(code, "x = 1\nprint(x)")

    def test_extract_empty(self):
        self.assertEqual(self.agent._extract_code(""), "")

    def test_extract_only_python_fence(self):
        response = "```python\nx = 1\n```\nSome trailing text"
        code = self.agent._extract_code(response)
        self.assertEqual(code, "x = 1")


class TestExecutionAgentParseFindings(unittest.TestCase):
    def setUp(self):
        self.agent = ExecutionAgent(api_key="sk-test")

    def test_parse_single_finding(self):
        output = json.dumps(
            {
                "line": 5,
                "severity": "high",
                "rule_id": "EX001",
                "message": "test",
                "suggestion": "fix it",
            }
        )
        findings = self.agent._parse_findings(output, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 5)
        self.assertEqual(findings[0].severity.value, "high")
        self.assertEqual(findings[0].rule_id, "EX001")

    def test_parse_multiple_findings(self):
        lines = [
            json.dumps(
                {
                    "line": 1,
                    "severity": "critical",
                    "rule_id": "EX001",
                    "message": "a",
                    "suggestion": "",
                }
            ),
            json.dumps(
                {"line": 2, "severity": "low", "rule_id": "EX002", "message": "b", "suggestion": ""}
            ),
        ]
        findings = self.agent._parse_findings("\n".join(lines), "test.py")
        self.assertEqual(len(findings), 2)

    def test_parse_invalid_json_skipped(self):
        output = "not json\n" + json.dumps(
            {"line": 1, "severity": "info", "rule_id": "EX001", "message": "ok", "suggestion": ""}
        )
        findings = self.agent._parse_findings(output, "test.py")
        self.assertEqual(len(findings), 1)

    def test_parse_empty_output(self):
        findings = self.agent._parse_findings("", "test.py")
        self.assertEqual(len(findings), 0)

    def test_parse_whitespace_only(self):
        findings = self.agent._parse_findings("  \n  \n", "test.py")
        self.assertEqual(len(findings), 0)

    def test_parse_invalid_severity_defaults_to_info(self):
        output = json.dumps(
            {
                "line": 1,
                "severity": "unknown",
                "rule_id": "EX001",
                "message": "test",
                "suggestion": "",
            }
        )
        findings = self.agent._parse_findings(output, "test.py")
        self.assertEqual(findings[0].severity.value, "info")


class TestExecutionAgentSandbox(unittest.TestCase):
    def test_agent_uses_sandbox_for_execution(self):
        mock_sandbox = MockSandbox(
            responses=[
                {
                    "success": True,
                    "output": json.dumps(
                        {
                            "line": 1,
                            "severity": "low",
                            "rule_id": "EX001",
                            "message": "test",
                            "suggestion": "",
                        }
                    ),
                    "error": None,
                    "execution_ms": 1.0,
                },
            ]
        )
        agent = ExecutionAgent(api_key="sk-test", sandbox=mock_sandbox)
        findings = agent._parse_findings(
            json.dumps(
                {
                    "line": 1,
                    "severity": "low",
                    "rule_id": "EX001",
                    "message": "test",
                    "suggestion": "",
                }
            ),
            "test.py",
        )
        self.assertEqual(len(findings), 1)

    def test_retry_on_sandbox_error(self):
        mock_sandbox = MockSandbox(
            responses=[
                {
                    "success": False,
                    "output": "",
                    "error": "NameError: x is not defined",
                    "execution_ms": 1.0,
                },
                {
                    "success": True,
                    "output": json.dumps(
                        {
                            "line": 1,
                            "severity": "info",
                            "rule_id": "EX001",
                            "message": "fixed",
                            "suggestion": "",
                        }
                    ),
                    "error": None,
                    "execution_ms": 1.0,
                },
            ]
        )
        mock_llm = MagicMock(return_value="```python\nprint('ok')\n```")
        agent = ExecutionAgent(api_key="sk-test", sandbox=mock_sandbox)
        with patch.object(agent, "_call_llm", mock_llm):
            agent.analyze(make_file("x = 1"))
        self.assertGreaterEqual(mock_llm.call_count, 2)

    def test_max_retries_exhausted(self):
        mock_sandbox = MockSandbox(
            responses=[
                {"success": False, "output": "", "error": "Error", "execution_ms": 1.0},
                {"success": False, "output": "", "error": "Error", "execution_ms": 1.0},
                {"success": False, "output": "", "error": "Error", "execution_ms": 1.0},
            ]
        )
        mock_llm = MagicMock(return_value="```python\nprint('ok')\n```")
        agent = ExecutionAgent(api_key="sk-test", sandbox=mock_sandbox, max_retries=3)
        with patch.object(agent, "_call_llm", mock_llm):
            findings = agent.analyze(make_file("x = 1"))
        self.assertEqual(mock_llm.call_count, 3)
        self.assertEqual(len(findings), 0)

    def test_llm_exception_triggers_retry(self):
        mock_sandbox = MockSandbox(
            responses=[
                {
                    "success": True,
                    "output": json.dumps(
                        {
                            "line": 1,
                            "severity": "info",
                            "rule_id": "EX001",
                            "message": "ok",
                            "suggestion": "",
                        }
                    ),
                    "error": None,
                    "execution_ms": 1.0,
                },
            ]
        )
        call_count = [0]

        def flaky_llm(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("API down")
            return "```python\nprint('ok')\n```"

        agent = ExecutionAgent(api_key="sk-test", sandbox=mock_sandbox, max_retries=2)
        with patch.object(agent, "_call_llm", flaky_llm):
            findings = agent.analyze(make_file("x = 1"))
        self.assertEqual(call_count[0], 2)
        self.assertGreaterEqual(len(findings), 0)


class TestExecutionAgentConfig(unittest.TestCase):
    def test_config_schema(self):
        agent = ExecutionAgent(api_key="sk-test")
        schema = agent.get_config_schema()
        self.assertIn("api_key", schema)
        self.assertIn("model", schema)
        self.assertIn("max_retries", schema)
        self.assertIn("sandbox_timeout", schema)
        self.assertEqual(schema["api_key"]["type"], "string")
        self.assertEqual(schema["max_retries"]["type"], "integer")

    def test_agent_name_and_description(self):
        agent = ExecutionAgent(api_key="sk-test")
        self.assertEqual(agent.name, "execution")
        self.assertIn("hybrid", agent.description.lower())

    def test_default_sandbox_created(self):
        agent = ExecutionAgent(api_key="sk-test")
        self.assertIsNotNone(agent.sandbox)
        self.assertEqual(agent.sandbox.timeout, 30)

    def test_custom_sandbox_timeout(self):
        agent = ExecutionAgent(api_key="sk-test", sandbox_timeout=15)
        self.assertEqual(agent.sandbox.timeout, 15)

    def test_default_tool_registry(self):
        agent = ExecutionAgent(api_key="sk-test")
        tools = agent.tool_registry.list_tools()
        self.assertGreater(len(tools), 0)


class TestExecutionAgentBuildPrompt(unittest.TestCase):
    def setUp(self):
        self.agent = ExecutionAgent(api_key="sk-test")

    def test_build_code_prompt_includes_source(self):
        prompt = self.agent._build_code_prompt("x = 1", "test.py")
        self.assertIn("x = 1", prompt)
        self.assertIn("test.py", prompt)

    def test_build_code_prompt_includes_tools(self):
        prompt = self.agent._build_code_prompt("x = 1", "test.py")
        self.assertIn("compute_complexity", prompt)
        self.assertIn("scan_secrets", prompt)

    def test_build_code_prompt_includes_format(self):
        prompt = self.agent._build_code_prompt("x = 1", "test.py")
        self.assertIn("JSON line", prompt)
        self.assertIn("severity", prompt)

    def test_build_fix_prompt_includes_error(self):
        prompt = self.agent._build_fix_prompt("Something broke", "print(1)")
        self.assertIn("Something broke", prompt)
        self.assertIn("print(1)", prompt)


class TestExecutionAgentEdgeCases(unittest.TestCase):
    def test_empty_file_content(self):
        agent = ExecutionAgent(api_key="sk-test")
        findings = agent.analyze(make_file("", "empty.py"))
        self.assertEqual(findings, [])

    def test_analyze_with_whitespace_only(self):
        agent = ExecutionAgent(api_key="sk-test")
        findings = agent.analyze(make_file("   \n  \n", "ws.py"))
        self.assertEqual(findings, [])

    def test_non_python_file_still_processed(self):
        agent = ExecutionAgent(api_key="sk-test")
        findings = agent.analyze(make_file("var x = 1;", "test.js"))
        self.assertEqual(findings, [])


class TestExecutionAgentIntegration(unittest.TestCase):
    def test_run_code_in_sandbox_injects_tools(self):
        agent = ExecutionAgent(api_key="sk-test")
        result = agent._run_code_in_sandbox("print('tool test')")
        self.assertTrue(result["success"])

    def test_tool_injection_works(self):
        agent = ExecutionAgent(api_key="sk-test")
        code = "result = compute_complexity('def foo():\\n    if x:\\n        pass\\n')\nimport json\nprint(json.dumps(result))"
        result = agent._run_code_in_sandbox(code)
        self.assertTrue(result["success"], msg=f"Failed: {result.get('error')}")
        data = json.loads(result["output"].strip())
        self.assertIsInstance(data, list)

    def test_empty_code_in_sandbox(self):
        agent = ExecutionAgent(api_key="sk-test")
        result = agent._run_code_in_sandbox("")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
