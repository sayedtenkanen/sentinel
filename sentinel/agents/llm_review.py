import json
import os

from sentinel.core.base_agent import BaseAgent
from sentinel.core.types import Finding, Severity


class LlmReviewAgent(BaseAgent):
    name = "llm-review"
    description = "Optional LLM-powered review using RAG context"

    def __init__(self, api_key="", model="", retriever=None):
        super().__init__(name=self.name)
        self.api_key = api_key or os.environ.get("SENTINEL_LLM_API_KEY", "")
        self.model = model or os.environ.get("SENTINEL_LLM_MODEL", "gpt-4o-mini")
        self.retriever = retriever

    def _check_available(self):
        return bool(self.api_key)

    def analyze(self, file):
        if not self._check_available():
            return []

        findings = []
        file_path = file.path
        source = file.content

        try:
            context_snippets = []
            if self.retriever:
                results = self.retriever.retrieve_context(source, top_k=3)
                context_snippets = results

            prompt = self._build_prompt(source, context_snippets, file_path)
            response = self._call_llm(prompt)
            parsed = self._parse_response(response)

            for finding_data in parsed:
                findings.append(
                    Finding(
                        file=file_path,
                        line=finding_data.get("line", 1),
                        column=0,
                        severity=Severity(finding_data.get("severity", "info").lower()),
                        rule_id=finding_data.get("rule_id", "LLM001"),
                        message=finding_data.get("message", ""),
                        suggestion=finding_data.get("suggestion", ""),
                    )
                )
        except Exception:
            pass

        return findings

    def _build_prompt(self, source, context_snippets, file_path):
        parts = [
            "You are a code review assistant. Review the following code and identify bugs,"
            " security vulnerabilities, performance issues, and style problems.",
            "",
            f"File: {file_path}",
            "```python",
            source,
            "```",
        ]

        if context_snippets and self.retriever:
            rag_context = self.retriever.build_prompt_context(context_snippets)
            if rag_context:
                parts.extend(["", rag_context])

        parts.extend(
            [
                "",
                "Respond with a JSON array of findings. Each finding must have:",
                '  - "line": int (line number or 1)',
                '  - "severity": string ("critical", "high", "medium", "low", "info")',
                '  - "rule_id": string (e.g. "LLM001")',
                '  - "message": string (short description)',
                '  - "suggestion": string (fix suggestion, optional)',
                "",
                "Return ONLY valid JSON, no markdown fences, no explanation outside the array.",
            ]
        )
        return "\n".join(parts)

    def _call_llm(self, prompt):
        import urllib.request

        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000,
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

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response):
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            return []

    def get_config_schema(self):
        return {
            "api_key": {"type": "string", "description": "OpenAI API key", "default": ""},
            "model": {"type": "string", "description": "Model name", "default": "gpt-4o-mini"},
            "rag_top_k": {
                "type": "integer",
                "description": "Number of RAG results to retrieve",
                "default": 3,
            },
        }
