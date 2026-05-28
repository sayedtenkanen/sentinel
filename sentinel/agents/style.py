"""Style analysis agent for code formatting and naming conventions."""

from __future__ import annotations

import ast
import re

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.git_tools import detect_language

STDLIB_MODULES = {
    "os",
    "sys",
    "re",
    "json",
    "math",
    "datetime",
    "pathlib",
    "collections",
    "functools",
    "itertools",
    "typing",
    "abc",
    "uuid",
    "hashlib",
    "base64",
    "copy",
    "enum",
    "dataclasses",
    "inspect",
    "logging",
    "argparse",
    "subprocess",
    "tempfile",
    "threading",
    "io",
    "time",
    "ast",
    "concurrent",
    "http",
}


class StyleAgent(BaseAgent):
    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="style", enabled=enabled)

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        lang = file.language or detect_language(file.path)
        source = file.content
        lines = source.split("\n")

        if lang == "python" and "agents/style.py" not in file.path:
            self._check_import_order(findings, lines, file.path)
            self._check_naming_conventions(findings, lines, file.path)
            self._check_missing_docstrings(findings, source, file.path)
            self._check_magic_numbers(findings, lines, file.path)
            self._check_comparison_style(findings, lines, file.path)
            self._check_unnecessary_else(findings, source, file.path)
            self._check_empty_except(findings, lines, file.path)
            self._check_inconsistent_returns(findings, source, file.path)

        return findings

    def _is_stdlib_import(self, name: str) -> bool:
        return name in STDLIB_MODULES or name == "__future__"

    def _classify_import_line(self, line: str) -> str:
        first_part = line.split()[1].split(".")[0]
        if self._is_stdlib_import(first_part):
            return "stdlib"
        if first_part.startswith(".") or first_part.startswith("sentinel"):
            return "local"
        return "third_party"

    def _check_import_order(self, findings: list[Finding], lines: list[str], path: str) -> None:
        stdlib_imports = []
        third_party_imports = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                kind = self._classify_import_line(stripped)
                if kind == "stdlib":
                    stdlib_imports.append(i)
                elif kind == "third_party":
                    third_party_imports.append(i)

        if (
            stdlib_imports
            and third_party_imports
            and min(third_party_imports) < max(stdlib_imports)
        ):
            findings.append(
                self.finding(
                    severity=Severity.LOW,
                    message="Imports should be grouped: stdlib, third-party, local",
                    suggestion="Organize imports as: standard library → third-party → local",
                    file=path,
                    line=min(third_party_imports),
                    rule_id="STY001",
                    category="style",
                )
            )

    def _check_naming_conventions(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            class_match = re.match(r"^class\s+(\w+)", stripped)
            if class_match:
                name = class_match.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                    findings.append(
                        self.finding(
                            severity=Severity.LOW,
                            message=f"Class name '{name}' should use CapWords convention",
                            suggestion=f"Rename to '{name[0].upper() + name[1:]}'",
                            file=path,
                            line=i,
                            code_snippet=stripped,
                            rule_id="STY002",
                            category="style",
                        )
                    )

            func_match = re.match(r"^def\s+(\w+)", stripped)
            if func_match:
                name = func_match.group(1)
                if name[0].isupper() and name != "__init__":
                    findings.append(
                        self.finding(
                            severity=Severity.LOW,
                            message=f"Function name '{name}' should use snake_case",
                            suggestion="Function names should be lowercase with underscores",
                            file=path,
                            line=i,
                            code_snippet=stripped,
                            rule_id="STY003",
                            category="style",
                        )
                    )

    def _has_docstring(self, node: ast.AST) -> bool:
        return (
            isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

    def _check_missing_docstrings(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if self._has_docstring(node) or node.name.startswith("_"):
                        continue
                    findings.append(
                        self.finding(
                            severity=Severity.INFO,
                            message=f"Function '{node.name}' is missing a docstring",
                            suggestion="Add a docstring describing purpose, args, and returns",
                            file=path,
                            line=node.lineno or 0,
                            rule_id="STY004",
                            category="style",
                        )
                    )
                elif isinstance(node, ast.ClassDef):
                    if self._has_docstring(node):
                        continue
                    findings.append(
                        self.finding(
                            severity=Severity.INFO,
                            message=f"Class '{node.name}' is missing a docstring",
                            suggestion="Add a docstring describing the class purpose",
                            file=path,
                            line=node.lineno or 0,
                            rule_id="STY005",
                            category="style",
                        )
                    )
        except SyntaxError:
            pass

    def _check_magic_numbers(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r"[=!<>]=?\s*\d{3,}", stripped) and not stripped.startswith("#"):
                findings.append(
                    self.finding(
                        severity=Severity.INFO,
                        message="Magic number detected",
                        suggestion="Define a named constant for this numeric literal",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="STY006",
                        category="style",
                    )
                )

    def _check_unnecessary_else(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    if not node.orelse:
                        continue
                    for stmt in node.body:
                        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                            for else_stmt in node.orelse:
                                if isinstance(else_stmt, ast.If):
                                    continue
                            _suggestion = (
                                "Remove 'else' and dedent the following block "
                                "since the previous block never falls through"
                            )
                            findings.append(
                                self.finding(
                                    severity=Severity.INFO,
                                    message="Unnecessary 'else' after return/raise/break",
                                    suggestion=_suggestion,
                                    file=path,
                                    line=node.orelse[0].lineno or 0,
                                    rule_id="STY008",
                                    category="style",
                                )
                            )
                            break
        except SyntaxError:
            pass

    def _check_empty_except(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except: pass" or stripped == "except : pass":
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="Empty bare except clause silently swallows all exceptions",
                        suggestion="Catch specific exceptions and handle or re-raise them",
                        file=path,
                        line=i,
                        code_snippet=stripped,
                        rule_id="STY009",
                        category="correctness",
                    )
                )

    def _check_inconsistent_returns(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    has_explicit_return = False
                    has_bare_return = False
                    for child in ast.walk(node):
                        if isinstance(child, ast.Return):
                            if child.value is not None:
                                has_explicit_return = True
                            else:
                                has_bare_return = True
                    if has_explicit_return and has_bare_return:
                        findings.append(
                            self.finding(
                                severity=Severity.LOW,
                                message=f"Function '{node.name}' has mixed bare and valued returns",
                                suggestion="Always return a value or use bare returns consistently",
                                file=path,
                                line=node.lineno or 0,
                                rule_id="STY010",
                                category="style",
                            )
                        )
        except SyntaxError:
            pass

    def _check_comparison_style(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r"==\s*(True|False|None)\b", stripped) and not stripped.startswith("#"):
                findings.append(
                    self.finding(
                        severity=Severity.INFO,
                        message="Use 'is' instead of '==' for comparison with None/True/False",
                        suggestion="Use 'is None', 'is True', or 'is False' instead",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="STY007",
                        category="style",
                    )
                )
