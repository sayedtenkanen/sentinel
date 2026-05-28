"""Static analysis agent for code complexity and quality metrics."""

from __future__ import annotations

import ast
import re

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.ast_tools import (
    compute_complexity,
    find_function_lengths,
    find_unused_imports,
)
from ..tools.git_tools import detect_language


class StaticAnalysisAgent(BaseAgent):
    def __init__(
        self,
        enabled: bool = True,
        complexity_threshold: int = 25,
        max_function_length: int = 50,
        max_line_length: int = 100,
        max_nesting_depth: int = 6,
        max_params: int = 8,
    ) -> None:
        super().__init__(name="static-analysis", enabled=enabled)
        self.complexity_threshold = complexity_threshold
        self.max_function_length = max_function_length
        self.max_line_length = max_line_length
        self.max_nesting_depth = max_nesting_depth
        self.max_params = max_params

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        lang = file.language or detect_language(file.path)
        lines = file.content.split("\n")
        source = file.content

        if lang != "python" or "agents/static_analysis.py" in file.path:
            return findings

        self._check_line_length(findings, lines, file.path)
        self._check_complexity(findings, source, file.path)
        self._check_function_length(findings, source, file.path)
        self._check_nesting(findings, source, file.path)
        self._check_unused_imports(findings, source, file.path)
        self._check_trailing_whitespace(findings, lines, file.path)
        self._check_blank_lines(findings, lines, file.path)
        self._check_too_many_params(findings, source, file.path)
        self._check_shadowed_builtins(findings, lines, file.path)

        return findings

    def _check_line_length(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            if len(line) > self.max_line_length:
                findings.append(
                    self.finding(
                        severity=Severity.LOW,
                        message=f"Line exceeds {self.max_line_length} characters ({len(line)})",
                        suggestion="Break line into multiple lines to improve readability",
                        file=path,
                        line=i,
                        code_snippet=line[:80],
                        rule_id="ST001",
                        category="style",
                    )
                )

    def _check_complexity(self, findings: list[Finding], source: str, path: str) -> None:
        complexity, _ = compute_complexity(source)
        if complexity > self.complexity_threshold:
            findings.append(
                self.finding(
                    severity=Severity.MEDIUM,
                    message=f"Complexity {complexity} (threshold: {self.complexity_threshold})",
                    suggestion="Refactor into smaller functions to reduce complexity",
                    file=path,
                    rule_id="ST002",
                    category="complexity",
                )
            )

    def _check_function_length(self, findings: list[Finding], source: str, path: str) -> None:
        for func in find_function_lengths(source):
            if func["length"] > self.max_function_length:
                _threshold = self.max_function_length
                _msg = f"Function '{func['name']}' is {func['length']} lines (limit: {_threshold})"
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message=_msg,
                        suggestion="Consider breaking this function into smaller units",
                        file=path,
                        line=func["line"],
                        rule_id="ST003",
                        category="complexity",
                    )
                )

    def _check_nesting(self, findings: list[Finding], source: str, path: str) -> None:
        _, max_nesting = compute_complexity(source)
        if max_nesting > self.max_nesting_depth:
            findings.append(
                self.finding(
                    severity=Severity.MEDIUM,
                    message=f"Nesting depth {max_nesting} (threshold: {self.max_nesting_depth})",
                    suggestion="Reduce nesting with guard clauses or helper functions",
                    file=path,
                    rule_id="ST004",
                    category="complexity",
                )
            )

    def _check_unused_imports(self, findings: list[Finding], source: str, path: str) -> None:
        for imp in find_unused_imports(source):
            findings.append(
                self.finding(
                    severity=Severity.LOW,
                    message=f"Unused import: '{imp['name']}'",
                    suggestion="Remove unused imports to keep the code clean",
                    file=path,
                    line=imp["line"],
                    rule_id="ST005",
                    category="style",
                )
            )

    def _check_trailing_whitespace(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            if line.rstrip("\n").endswith((" ", "\t")):
                findings.append(
                    self.finding(
                        severity=Severity.INFO,
                        message="Trailing whitespace detected",
                        suggestion="Remove trailing whitespace",
                        file=path,
                        line=i,
                        rule_id="ST006",
                        category="style",
                    )
                )

    def _check_blank_lines(self, findings: list[Finding], lines: list[str], path: str) -> None:
        blank_count = 0
        for i, line in enumerate(lines):
            if not line.strip():
                blank_count += 1
            else:
                if blank_count > 3:
                    findings.append(
                        self.finding(
                            severity=Severity.INFO,
                            message=f"Excessive blank lines ({blank_count}) before line {i + 1}",
                            suggestion="Max 2 blank lines between defs, 1 between methods",
                            file=path,
                            line=i + 1,
                            rule_id="ST007",
                            category="style",
                        )
                    )
                blank_count = 0

    def _check_too_many_params(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    param_count = len(node.args.args) + len(node.args.kwonlyargs)
                    if node.args.vararg:
                        param_count += 1
                    if node.args.kwarg:
                        param_count += 1
                    if param_count > self.max_params:
                        findings.append(
                            self.finding(
                                severity=Severity.MEDIUM,
                                message=f"'{node.name}' has {param_count} params (limit: {self.max_params})",
                                suggestion="Use a dataclass or split into smaller functions",
                                file=path,
                                line=node.lineno or 0,
                                rule_id="ST008",
                                category="complexity",
                            )
                        )
        except SyntaxError:
            pass

    def _check_shadowed_builtins(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        builtins = {
            "list",
            "dict",
            "str",
            "int",
            "float",
            "bool",
            "set",
            "tuple",
            "type",
            "object",
            "input",
            "print",
            "len",
            "range",
            "map",
            "filter",
            "zip",
            "open",
            "file",
            "id",
            "eval",
            "exec",
            "max",
            "min",
            "sum",
            "any",
            "all",
            "abs",
            "round",
            "sorted",
            "reversed",
            "enumerate",
            "iter",
            "next",
            "property",
            "staticmethod",
            "classmethod",
            "super",
            "Exception",
            "BaseException",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "AttributeError",
            "ImportError",
        }
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            match = re.match(
                r"(?:class|def)\s+(" + "|".join(sorted(builtins, key=len, reverse=True)) + r")\b",
                stripped,
            )
            if match:
                name = match.group(1)
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message=f"Name '{name}' shadows Python built-in",
                        suggestion=f"Rename '{name}' to avoid shadowing the built-in",
                        file=path,
                        line=i,
                        code_snippet=stripped,
                        rule_id="ST009",
                        category="correctness",
                    )
                )
