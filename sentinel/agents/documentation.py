"""Documentation analysis agent for checking docstring coverage and quality."""

from __future__ import annotations

import re

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..parsers import NullParser, default_registry
from ..parsers.base import BaseParser
from ..tools.git_tools import detect_language


class DocumentationAgent(BaseAgent):
    def __init__(self, enabled: bool = True, parser: BaseParser | None = None) -> None:
        super().__init__(name="documentation", enabled=enabled)
        self.parser = parser or NullParser()
        self.redundant_comment_patterns = [
            (r"#\s*(increment|decrement)\s+\w+", "Descriptive comment on simple mutation"),
            (r"#\s*(set|get)\s+", "Trivial getter/setter comment"),
            (r"#\s*(return|loop|iterate|call)\s", "Obvious action commented"),
            (r"#\s*(add|remove|update)\s+", "Trivial operation commented"),
            (r"#\s*initialize\s+\w+", "Self-explanatory initialization"),
        ]

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        lang = file.language or detect_language(file.path)
        source = file.content
        lines = source.split("\n")

        if lang == "python":
            if isinstance(self.parser, NullParser):
                self.parser = default_registry().get_or_default(lang)
            self._check_module_docstring(findings, source, file.path)
            self._check_redundant_comments(findings, lines, file.path)
            self._check_stale_comments(findings, lines, file.path)
            self._check_todo_density(findings, lines, file.path)
            self._check_docstring_params(findings, source, file.path)
            self._check_too_few_comments(findings, lines, file.path)

        return findings

    def _check_module_docstring(self, findings: list[Finding], source: str, path: str) -> None:
        if not self.parser.find_module_has_docstring(source) and len(source.split("\n")) > 20:
            findings.append(
                self.finding(
                    severity=Severity.LOW,
                    message="Module is missing a top-level docstring",
                    suggestion="Add a module-level docstring describing this file's purpose",
                    file=path,
                    line=1,
                    rule_id="DOC001",
                    category="documentation",
                )
            )

    def _check_redundant_comments(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            for pattern, description in self.redundant_comment_patterns:
                if re.search(pattern, stripped, re.IGNORECASE):
                    findings.append(
                        self.finding(
                            severity=Severity.INFO,
                            message=f"Redundant comment: {description}",
                            suggestion="Remove comment if obvious; explain intent, not action",
                            file=path,
                            line=i,
                            code_snippet=stripped[:60],
                            rule_id="DOC002",
                            category="documentation",
                        )
                    )
                    break

    def _check_stale_comments(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(
                r"#\s*(old|legacy|deprecated|hack|workaround|temporary|quick\s*(and\s*dirty|fix))",
                stripped,
                re.IGNORECASE,
            ):
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="Possibly stale/debt comment detected",
                        suggestion="Review if this still applies; clean up legacy workarounds",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="DOC003",
                        category="documentation",
                    )
                )

    def _check_todo_density(self, findings: list[Finding], lines: list[str], path: str) -> None:
        todo_count = 0
        total_lines = len(lines)
        for line in lines:
            if re.search(r"#\s*(TODO|FIXME|HACK|XXX)", line, re.IGNORECASE):
                todo_count += 1

        if todo_count > 0 and total_lines > 0:
            density = todo_count / total_lines
            if density > 0.03 and todo_count >= 3:
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message=f"TODO/FIXME density: {todo_count}/{total_lines} ({density:.0%})",
                        suggestion="Address outstanding TODOs and FIXMEs before they become stale",
                        file=path,
                        rule_id="DOC004",
                        category="documentation",
                    )
                )

    def _check_docstring_params(self, findings: list[Finding], source: str, path: str) -> None:
        for item in self.parser.find_undocumented_params(source):
            findings.append(
                self.finding(
                    severity=Severity.LOW,
                    message=f"Parameter '{item.param}' in '{item.function}()' undocumented",
                    suggestion=f"Add ':param {item.param}: ...' describing the param",
                    file=path,
                    line=item.line,
                    rule_id="DOC005",
                    category="documentation",
                )
            )

    def _check_too_few_comments(self, findings: list[Finding], lines: list[str], path: str) -> None:
        comment_lines = 0
        code_lines = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                comment_lines += 1
            elif not stripped.startswith("#"):
                code_lines += 1

        if code_lines > 50 and comment_lines == 0:
            findings.append(
                self.finding(
                    severity=Severity.INFO,
                    message=f"File has {code_lines} lines of code but zero comments",
                    suggestion="Add comments explaining complex logic and non-obvious behavior",
                    file=path,
                    rule_id="DOC006",
                    category="documentation",
                )
            )
