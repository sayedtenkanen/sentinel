"""Hybrid execution agent with decision policy, sandboxed code, and iterative fix loop.

Implements the production template's hybrid model:
  - Decision policy: route between direct tools and sandboxed code execution
  - Sandboxed code: LLM writes Python, executes in restricted sandbox
  - Iterative fix loop: parse errors → rewrite → re-execute (capped retries)
  - Safety: injected tools only, blocked unsafe operations
"""

from __future__ import annotations

import json
import os

from sentinel.core.base_agent import BaseAgent
from sentinel.core.types import FileContext, Finding, Severity
from sentinel.tools.sandbox import Sandbox
from sentinel.tools.tool_registry import ToolRegistry, default_registry

ANALYSIS_TEMPLATE = """You are a code analysis agent. You have access to these tools:

{tools_help}

Write a Python script that analyzes the code below and prints findings.
Each finding must be printed as a JSON line with this format:
  {{"line": <int>, "severity": "<critical|high|medium|low|info>", "rule_id": "<ID>", "message": "<desc>", "suggestion": "<fix>"}}

Use the injected tools above to analyze the code. Import them directly (they are in global scope).

Code to analyze ({file_path}):
```python
{source_code}
```

Rules:
- Print each finding as a separate JSON line using print(json.dumps(...))
- Do NOT use markdown fences in output
- Use try/except for robust error handling
- Keep logic deterministic
- Only use injected functions and allowed modules

Output ONLY the JSON lines, nothing else."""

FIX_TEMPLATE = """The previous script had an error:

{error}

Here is the script that failed:
```python
{failed_code}
```

Rewrite the script to fix the error. Follow the same output format.
Output ONLY valid JSON lines, no explanation."""


class ExecutionAgent(BaseAgent):
    name = "execution"
    description = (
        "Hybrid execution agent: direct tools + sandboxed Python for cross-cutting analysis"
    )

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        sandbox: Sandbox | None = None,
        tool_registry: ToolRegistry | None = None,
        max_retries: int = 3,
        sandbox_timeout: int = 30,
    ) -> None:
        super().__init__(name=self.name)
        self.api_key = api_key or os.environ.get("SENTINEL_LLM_API_KEY", "")
        self.model = model or os.environ.get("SENTINEL_LLM_MODEL", "gpt-4o-mini")
        self.sandbox = sandbox or Sandbox(timeout=sandbox_timeout)
        self.tool_registry = tool_registry or default_registry()
        self.max_retries = max_retries
        self.sandbox_timeout = sandbox_timeout

    def _check_available(self) -> bool:
        return bool(self.api_key)

    def _call_llm(self, prompt: str) -> str:
        import urllib.request

        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 4000,
            }
        ).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"]

    def _parse_findings(self, output: str, file_path: str) -> list[Finding]:
        findings: list[Finding] = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            raw_severity = data.get("severity", "info")
            try:
                severity = Severity(str(raw_severity).lower())
            except ValueError:
                severity = Severity.INFO
            findings.append(
                Finding(
                    file=file_path,
                    line=data.get("line", 1),
                    severity=severity,
                    rule_id=data.get("rule_id", "EX001"),
                    message=data.get("message", ""),
                    suggestion=data.get("suggestion", ""),
                )
            )
        return findings

    def _build_code_prompt(self, source: str, file_path: str) -> str:
        tools_help = self.tool_registry.get_help()
        return ANALYSIS_TEMPLATE.format(
            tools_help=tools_help,
            source_code=source,
            file_path=file_path,
        )

    def _build_fix_prompt(self, error: str, failed_code: str) -> str:
        return FIX_TEMPLATE.format(error=error, failed_code=failed_code)

    def _run_code_in_sandbox(self, code: str, inject: dict | None = None) -> dict:
        tool_fns: dict[str, object] = {t.name: t.fn for t in self.tool_registry.list_tools()}
        if inject:
            tool_fns.update(inject)
        return self.sandbox.execute(code, inject=tool_fns, timeout=self.sandbox_timeout)

    def analyze(self, file: FileContext) -> list[Finding]:
        if not self._check_available():
            return []

        if not file.content:
            return []

        findings: list[Finding] = []
        prompt = self._build_code_prompt(file.content, file.path)

        for _ in range(self.max_retries):
            try:
                response = self._call_llm(prompt)
                code = self._extract_code(response)
                if not code:
                    continue
                result = self._run_code_in_sandbox(code, inject={"file_path": file.path})
                if result["success"]:
                    findings = self._parse_findings(result["output"], file.path)
                    break
                prompt = self._build_fix_prompt(result.get("error", "Unknown error"), code)
            except Exception as exc:
                prompt = self._build_fix_prompt(f"Exception: {exc}", prompt)

        return findings

    def _extract_code(self, response: str) -> str:
        cleaned = response.strip()
        if "```python" in cleaned:
            parts = cleaned.split("```python", 1)
            if len(parts) > 1:
                cleaned = parts[1]
                if "```" in cleaned:
                    cleaned = cleaned.split("```", 1)[0]
        elif "```" in cleaned:
            parts = cleaned.split("```", 2)
            if len(parts) >= 2:
                cleaned = parts[1]
                if "```" in cleaned:
                    cleaned = cleaned.split("```", 1)[0]
        return cleaned.strip()

    def get_config_schema(self) -> dict:
        return {
            "api_key": {"type": "string", "description": "LLM API key", "default": ""},
            "model": {"type": "string", "description": "Model name", "default": "gpt-4o-mini"},
            "max_retries": {"type": "integer", "description": "Max code fix retries", "default": 3},
            "sandbox_timeout": {
                "type": "integer",
                "description": "Sandbox timeout in seconds",
                "default": 30,
            },
        }
