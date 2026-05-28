"""Best practices analysis agent for detecting common anti-patterns."""

from __future__ import annotations

import ast
import re

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.git_tools import detect_language


class BestPracticesAgent(BaseAgent):
    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="best-practices", enabled=enabled)

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        lang = file.language or detect_language(file.path)
        source = file.content
        lines = source.split("\n")

        if lang == "python" and "agents/best_practices.py" not in file.path:
            self._check_bare_excepts(findings, source, file.path)
            self._check_lambda_assignments(findings, lines, file.path)
            self._check_mutable_defaults(findings, source, file.path)
            self._check_global_vars(findings, lines, file.path)
            self._check_type_hints(findings, source, file.path)
            self._check_meaningless_variables(findings, lines, file.path)
            self._check_context_manager_usage(findings, lines, file.path)
            self._check_type_comparison(findings, lines, file.path)
            self._check_dict_iteration(findings, lines, file.path)

        return findings

    def _check_bare_excepts(self, findings: list[Finding], source: str, path: str) -> None:
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("except:") or stripped.startswith("except :"):
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="Bare except catches all, incl. SystemExit & KeyboardInterrupt",
                        suggestion="Catch specific exceptions (e.g., except Exception:)",
                        file=path,
                        line=i,
                        code_snippet=stripped,
                        rule_id="BP001",
                        category="error-handling",
                    )
                )

    def _check_lambda_assignments(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r"^\w+\s*=\s*lambda\s", stripped) and not stripped.startswith("#"):
                findings.append(
                    self.finding(
                        severity=Severity.LOW,
                        message="Lambda assigned to variable instead of def",
                        suggestion="Use 'def' instead of assigning lambda to a variable",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="BP002",
                        category="style",
                    )
                )

    def _check_mutable_defaults(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            _suggestion = "Set default to None; init list/dict/set in function body"
                            findings.append(
                                self.finding(
                                    severity=Severity.HIGH,
                                    message=f"Mutable default argument in '{node.name}'",
                                    suggestion=_suggestion,
                                    file=path,
                                    line=default.lineno or 0,
                                    rule_id="BP003",
                                    category="correctness",
                                )
                            )
        except SyntaxError:
            pass

    def _check_global_vars(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("global "):
                _suggestion = "Pass as params or use class attributes instead of global"
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="Use of 'global' keyword",
                        suggestion=_suggestion,
                        file=path,
                        line=i,
                        code_snippet=stripped,
                        rule_id="BP004",
                        category="design",
                    )
                )

    def _check_type_hints(self, findings: list[Finding], source: str, path: str) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    returns_hint = node.returns is not None
                    params_hint = all(
                        arg.annotation is not None or arg.arg == "self" for arg in node.args.args
                    )
                    if not returns_hint or not params_hint:
                        findings.append(
                            self.finding(
                                severity=Severity.INFO,
                                message=f"Function '{node.name}' is missing type hints",
                                suggestion="Add type hints for parameters and return value",
                                file=path,
                                line=node.lineno or 0,
                                rule_id="BP005",
                                category="maintainability",
                            )
                        )
        except SyntaxError:
            pass

    def _check_meaningless_variables(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            match = re.match(
                r"^(\w+)\s*=\s*['\"]([^'\"]*)['\"]\s*#\s*(TODO|FIXME|HACK|XXX)", stripped
            )
            if match:
                findings.append(
                    self.finding(
                        severity=Severity.INFO,
                        message=f"Placeholder '{match.group(1)}' with {match.group(3)} marker",
                        suggestion="Implement or remove the placeholder value",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="BP006",
                        category="maintainability",
                    )
                )

    def _check_context_manager_usage(
        self, findings: list[Finding], lines: list[str], path: str
    ) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if (
                not stripped.startswith("with")
                and re.search(r"(?<!\.)\bopen\s*\(", stripped)
                and not stripped.startswith("#")
            ):
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="File opened without context manager",
                        suggestion="Use 'with open(...) as f:' to ensure proper resource cleanup",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="BP007",
                        category="correctness",
                    )
                )

    def _check_type_comparison(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(
                r"type\s*\(\s*\w+\s*\)\s*(==|!=|is)\s", stripped
            ) and not stripped.startswith("#"):
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM,
                        message="Type comparison should use isinstance() instead of type()",
                        suggestion="Use isinstance(x, SomeClass) instead of type(x) == SomeClass",
                        file=path,
                        line=i,
                        code_snippet=stripped[:60],
                        rule_id="BP008",
                        category="correctness",
                    )
                )

    def _check_dict_iteration(self, findings: list[Finding], lines: list[str], path: str) -> None:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            match = re.match(r"\s*for\s+(\w+)\s+in\s+(\w+)\.keys\(\)\s*:", stripped)
            if match:
                key_var = match.group(1)
                dict_var = match.group(2)
                _msg = f"Iterate {dict_var}.keys() - use .items() if values needed"
                _sug = f"Use 'for {key_var}, v in {dict_var}.items():' for key & val"
                findings.append(
                    self.finding(
                        severity=Severity.INFO,
                        message=_msg,
                        suggestion=_sug,
                        file=path,
                        line=i,
                        code_snippet=stripped,
                        rule_id="BP009",
                        category="performance",
                    )
                )
