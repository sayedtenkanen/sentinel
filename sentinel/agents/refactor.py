"""Refactor opportunity detection — cross-function analysis for refactoring targets.

Deterministic agent that identifies functions with high refactor priority
based on complexity, length, parameter count, and nesting depth.
"""

from __future__ import annotations

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.ast_tools import find_function_lengths


class RefactorAgent(BaseAgent):
    name = "refactor"
    description = "Refactor opportunity detection: complex, long, overloaded functions"

    def __init__(
        self,
        enabled: bool = True,
        complexity_weight: float = 2.0,
        length_weight: float = 1.0,
        param_weight: float = 1.5,
        refactor_threshold: float = 20.0,
    ) -> None:
        super().__init__(name=self.name, enabled=enabled)
        self.complexity_weight = complexity_weight
        self.length_weight = length_weight
        self.param_weight = param_weight
        self.refactor_threshold = refactor_threshold

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        source = file.content
        if not source.strip():
            return findings

        functions = find_function_lengths(source)

        for func in functions:
            score = self._compute_refactor_score(func)
            if score >= self.refactor_threshold:
                line = func.get("line", 1)
                findings.append(
                    self.finding(
                        severity=Severity.MEDIUM if score < 30 else Severity.HIGH,
                        message=(
                            f"Refactor opportunity: {func['name']} "
                            f"(complexity={func.get('complexity', '?')}, "
                            f"length={func['length']} lines, score={score:.1f})"
                        ),
                        suggestion=(
                            f"Consider splitting {func['name']} into smaller functions. "
                            f"Refactor score {score:.1f} exceeds threshold {self.refactor_threshold}"
                        ),
                        file=file.path,
                        line=line,
                        rule_id="REF001",
                        category="refactor",
                    )
                )

        if findings:
            top_score = max(self._compute_refactor_score(f) for f in functions)
            if top_score >= self.refactor_threshold * 2:
                findings.append(
                    self.finding(
                        severity=Severity.CRITICAL,
                        message=(f"High-priority refactor target: highest score {top_score:.1f}"),
                        suggestion="File exceeds refactor threshold by 2x. Consider full rewrite",
                        file=file.path,
                        line=1,
                        rule_id="REF002",
                        category="refactor",
                    )
                )

        return findings

    def _compute_refactor_score(self, func: dict) -> float:
        c_score = func.get("complexity", 1) * self.complexity_weight
        l_score = func.get("length", 0) * self.length_weight
        p_score = func.get("params", 0) * self.param_weight
        return c_score + l_score + p_score

    def get_config_schema(self) -> dict:
        return {
            "complexity_weight": {
                "type": "float",
                "default": 2.0,
                "description": "Weight for cyclomatic complexity in refactor score",
            },
            "length_weight": {
                "type": "float",
                "default": 1.0,
                "description": "Weight for function length in refactor score",
            },
            "param_weight": {
                "type": "float",
                "default": 1.5,
                "description": "Weight for parameter count in refactor score",
            },
            "refactor_threshold": {
                "type": "float",
                "default": 20.0,
                "description": "Minimum score to flag refactor opportunity",
            },
        }
