"""Orchestrator for coordinating sub-agents and collecting results."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..agents.best_practices import BestPracticesAgent
from ..agents.documentation import DocumentationAgent
from ..agents.security import SecurityAgent
from ..agents.static_analysis import StaticAnalysisAgent
from ..agents.style import StyleAgent
from ..agents.summary import SummaryAgent
from ..govern.cost import CostTracker
from ..monitor.tracer import Tracer
from ..rag.retriever import Retriever
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
    """Coordinates sub-agents, manages parallelism, tracing, and cost tracking."""

    def __init__(
        self,
        agents: list[BaseAgent] | None = None,
        tracer: Tracer | None = None,
        cost_tracker: CostTracker | None = None,
        max_workers: int | None = None,
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
        self.max_workers = max_workers
        self.retriever: Retriever | None = None

    def set_retriever(self, retriever: Retriever | None) -> None:
        self.retriever = retriever

    def review(self, context: ReviewContext) -> ReviewReport:
        """Run all agents on all files in the context.

        context: ReviewContext with files and scope to review.
        """
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

        parallel = self.max_workers and self.max_workers > 1 and len(context.files) > 1

        if parallel:
            with (
                ThreadPoolExecutor(max_workers=self.max_workers) as file_pool,
                ThreadPoolExecutor(max_workers=self.max_workers) as agent_pool,
            ):
                futures = {}
                for file in context.files:
                    if self.cost_tracker.cap_exceeded:
                        break
                    futures[file_pool.submit(self._review_file, file, agent_pool)] = file

                for future in as_completed(futures):
                    file = futures[future]
                    try:
                        report.agent_results.extend(future.result())
                    except Exception as e:
                        self._trace_file_failed(file, str(e))
        else:
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
                try:
                    file_result = self._review_file(file)
                    report.agent_results.extend(file_result)
                except Exception as e:
                    self._trace_file_failed(file, str(e))

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

    def _trace_file_failed(self, file: FileContext, error: str) -> None:
        self.tracer.trace(
            TraceEvent(
                agent_name="orchestrator",
                event="review.file_failed",
                metadata={"file": file.path, "error": error},
            )
        )

    def _review_file(
        self, file: FileContext, agent_pool: ThreadPoolExecutor | None = None
    ) -> list[AgentResult]:
        results: list[AgentResult] = []

        if agent_pool:
            agent_futures = {
                agent_pool.submit(self._run_agent, agent, file): (i, agent)
                for i, agent in enumerate(self.agents)
            }
            by_index: dict[int, AgentResult] = {}
            for future in as_completed(agent_futures):
                i, agent = agent_futures[future]
                try:
                    by_index[i] = future.result()
                except Exception as e:
                    by_index[i] = AgentResult(
                        agent_name=agent.name,
                        status=AgentStatus.FAILED,
                        error=str(e),
                    )
            results = [by_index[i] for i in range(len(self.agents))]
        else:
            for agent in self.agents:
                try:
                    results.append(self._run_agent(agent, file))
                except Exception as e:
                    results.append(
                        AgentResult(
                            agent_name=agent.name,
                            status=AgentStatus.FAILED,
                            error=str(e),
                        )
                    )

        return results

    def _run_agent(self, agent: BaseAgent, file: FileContext) -> AgentResult:
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
        return result

    def summarize(self, report: ReviewReport) -> str:
        """Produce a human-readable summary string for the report.

        report: ReviewReport to summarize.
        """
        return self.summary_agent.summarize(report, self.cost_tracker.report.summary_line())

    def get_agent_report(self, name: str, report: ReviewReport) -> AgentResult | None:
        """Look up an agent's results by name from the report.

        name: Agent name to look up.
        report: ReviewReport containing agent results.
        """
        for result in report.agent_results:
            if result.agent_name == name:
                return result
        return None
