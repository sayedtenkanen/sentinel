"""Abstract base class for all sentinel agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from .types import (
    AgentResult,
    AgentStatus,
    FileContext,
    Finding,
    Severity,
    TraceEvent,
)


class BaseAgent(ABC):
    def __init__(self, name: str, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def analyze(self, file: FileContext) -> list[Finding]: ...

    def run(self, file: FileContext) -> AgentResult:
        start = time.perf_counter()
        trace = TraceEvent(agent_name=self.name, event="run.started")

        try:
            if not self.enabled:
                result = AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.COMPLETED,
                    findings=[],
                )
            else:
                findings = self.analyze(file)
                result = AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.COMPLETED,
                    findings=findings,
                )
        except Exception as e:
            result = AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(e),
            )

        elapsed = (time.perf_counter() - start) * 1000
        result.duration_ms = elapsed
        trace.duration_ms = elapsed
        trace.event = f"run.{'completed' if result.status == AgentStatus.COMPLETED else 'failed'}"
        return result

    def finding(
        self,
        severity: Severity,
        message: str,
        suggestion: str = "",
        file: str = "",
        line: int | None = None,
        column: int | None = None,
        code_snippet: str | None = None,
        rule_id: str = "",
        category: str = "",
    ) -> Finding:
        return Finding(
            agent_name=self.name,
            severity=severity,
            message=message,
            suggestion=suggestion,
            file=file,
            line=line,
            column=column,
            code_snippet=code_snippet,
            rule_id=rule_id,
            category=category,
        )
