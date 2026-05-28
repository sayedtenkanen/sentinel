"""Documentation analysis agent for checking docstring coverage and quality."""

from __future__ import annotations

import ast
import re

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.git_tools import detect_language


class DocumentationAgent(BaseAgent):
    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="documentation", enabled=enabled)
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
            self._check_module_docstring(findings, source, file.path)
            self._check_redundant_comments(findings, lines, file.path)
            self._check_stale_comments(findings, lines, file.path)
            self._check_todo_density(findings, lines, file.path)
            self._check_docstring_params(findings, source, file.path)
            self._check_too_few_comments(findings, lines, file.path)

        return findings

    def _check_module_docstring(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            if not tree.body:
                return
            has_docstring = (
                isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            )
            if not has_docstring and len(source.split("\n")) > 20:
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
        except SyntaxError:
            pass

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
        """Check for docstring parameter documentation accuracy.

        findings: List to append undocumented param findings to.
        source: Source code to scan.
        path: File path for finding attribution.
        """
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.body:
                        continue
                    first_stmt = node.body[0]
                    has_docstring = (
                        isinstance(first_stmt, ast.Expr)
                        and isinstance(first_stmt.value, ast.Constant)
                        and isinstance(first_stmt.value.value, str)
                    )
                    if not has_docstring:
                        continue

                    doc = first_stmt.value.value
                    actual_params = {
                        arg.arg for arg in node.args.args if arg.arg != "self" and arg.arg != "cls"
                    }

                    doc_params = set(re.findall(r"^\s*([\w_]+)\s*:", doc, re.MULTILINE))

                    missing_from_doc = actual_params - doc_params
                    if missing_from_doc and node.name != "__init__":
                        for param in sorted(missing_from_doc):
                            findings.append(
                                self.finding(
                                    severity=Severity.LOW,
                                    message=f"Parameter '{param}' in '{node.name}()' undocumented",
                                    suggestion=f"Add ':param {param}: ...' describing the param",
                                    file=path,
                                    line=node.lineno or 0,
                                    rule_id="DOC005",
                                    category="documentation",
                                )
                            )

        except SyntaxError:
            pass

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
