"""Orchestrator for coordinating sub-agents and collecting results."""

from __future__ import annotations

import time

from ..agents.best_practices import BestPracticesAgent
from ..agents.documentation import DocumentationAgent
from ..agents.security import SecurityAgent
from ..agents.static_analysis import StaticAnalysisAgent
from ..agents.style import StyleAgent
from ..agents.summary import SummaryAgent
from ..govern.cost import CostTracker
from ..monitor.tracer import Tracer
from .base_agent import BaseAgent
from .context import ReviewContext
from .types import (
    AgentResult,
    AgentStatus,
    FileContext,
    ReviewReport,
    TraceEvent,
)


class Orchestrator:
    def __init__(
        self,
        agents: list[BaseAgent] | None = None,
        tracer: Tracer | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self.agents = agents or [
            StaticAnalysisAgent(),
            SecurityAgent(),
            StyleAgent(),
            BestPracticesAgent(),
            DocumentationAgent(),
        ]
        self.summary_agent = SummaryAgent()
        self.tracer = tracer or Tracer()
        self.cost_tracker = cost_tracker or CostTracker()

    def review(self, context: ReviewContext) -> ReviewReport:
        start = time.perf_counter()
        report = ReviewReport(
            scope=context.scope,
            files_reviewed=context.files,
        )

        self.tracer.trace(
            TraceEvent(
                agent_name="orchestrator",
                event="review.started",
                metadata={"files": len(context.files), "scope": context.scope.value},
            )
        )

        for file in context.files:
            if self.cost_tracker.cap_exceeded:
                self.tracer.trace(
                    TraceEvent(
                        agent_name="orchestrator",
                        event="review.cap_reached",
                        metadata={
                            "cost": self.cost_tracker.total_cost,
                            "cap": self.cost_tracker.cost_cap,
                        },
                    )
                )
                break
            file_result = self._review_file(file, context)
            report.agent_results.extend(file_result)

        report.duration_ms = (time.perf_counter() - start) * 1000

        self.tracer.trace(
            TraceEvent(
                agent_name="orchestrator",
                event="review.completed",
                duration_ms=report.duration_ms,
                metadata={
                    "findings": len(report.all_findings),
                    "score": report.score,
                    "total_cost": self.cost_tracker.total_cost,
                    "cost_cap": self.cost_tracker.cost_cap,
                },
            )
        )

        return report

    def _review_file(self, file: FileContext, _context: ReviewContext) -> list[AgentResult]:
        results: list[AgentResult] = []

        for agent in self.agents:
            self.tracer.trace(
                TraceEvent(
                    agent_name=agent.name,
                    event="run.started",
                    metadata={"file": file.path},
                )
            )
            result = agent.run(file)
            self.cost_tracker.track(agent.name, result.duration_ms)
            _event = f"run.{'completed' if result.status == AgentStatus.COMPLETED else 'failed'}"
            self.tracer.trace(
                TraceEvent(
                    agent_name=agent.name,
                    event=_event,
                    duration_ms=result.duration_ms,
                    metadata={
                        "findings": len(result.findings),
                        "file": file.path,
                        "error": result.error,
                    },
                )
            )
            results.append(result)

        return results

    def summarize(self, report: ReviewReport) -> str:
        return self.summary_agent.summarize(report, self.cost_tracker.report.summary_line())

    def get_agent_report(self, name: str, report: ReviewReport) -> AgentResult | None:
        for result in report.agent_results:
            if result.agent_name == name:
                return result
        return None
