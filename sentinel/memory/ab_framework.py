"""A/B framework for comparing reviews with and without memory.

Runs the same review twice (with and without memory context) and
produces a comparison report showing memory impact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.context import ReviewContext
from ..core.types import ReviewReport


@dataclass
class ABConfig:
    """Configuration for A/B comparison."""

    run_with_memory: bool = True
    run_without_memory: bool = True
    memory_context: dict | None = None


@dataclass
class ABResult:
    """Result of A/B comparison."""

    with_memory: ReviewReport | None = None
    without_memory: ReviewReport | None = None
    comparison: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""


class ABFramework:
    """Compares review quality with and without memory.

    Usage:
        framework = ABFramework()
        result = framework.compare(context, orchestrator_factory, memory_context)
    """

    def compare(
        self,
        context: ReviewContext,
        orchestrator_factory: Any,
        memory_context: dict | None = None,
    ) -> ABResult:
        """Run A/B comparison."""
        result = ABResult()

        if memory_context:
            orch_with = orchestrator_factory(memory_context=memory_context)
            result.with_memory = orch_with.review(context)

        orch_without = orchestrator_factory(memory_context=None)
        result.without_memory = orch_without.review(context)

        result.comparison = self._compare_reports(result.with_memory, result.without_memory)
        result.recommendation = self._generate_recommendation(result.comparison)

        return result

    def _compare_reports(
        self, with_mem: ReviewReport | None, without_mem: ReviewReport | None
    ) -> dict[str, Any]:
        """Compare two reports and generate metrics."""
        comparison: dict[str, Any] = {}

        with_findings = len(with_mem.all_findings) if with_mem else 0
        without_findings = len(without_mem.all_findings) if without_mem else 0

        comparison["findings_with_memory"] = with_findings
        comparison["findings_without_memory"] = without_findings
        comparison["findings_delta"] = without_findings - with_findings

        with_score = with_mem.score if with_mem else 0
        without_score = without_mem.score if without_mem else 0
        comparison["score_with_memory"] = with_score
        comparison["score_without_memory"] = without_score
        comparison["score_delta"] = with_score - without_score

        with_duration = with_mem.duration_ms if with_mem else 0
        without_duration = without_mem.duration_ms if without_mem else 0
        comparison["duration_with_memory"] = with_duration
        comparison["duration_without_memory"] = without_duration
        comparison["duration_delta_ms"] = without_duration - with_duration

        with_severities = self._severity_breakdown(with_mem) if with_mem else {}
        without_severities = self._severity_breakdown(without_mem) if without_mem else {}
        comparison["severity_with_memory"] = with_severities
        comparison["severity_without_memory"] = without_severities

        return comparison

    def _severity_breakdown(self, report: ReviewReport) -> dict[str, int]:
        """Count findings by severity."""
        breakdown: dict[str, int] = {}
        for finding in report.all_findings:
            sev = (
                finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity)
            )
            breakdown[sev] = breakdown.get(sev, 0) + 1
        return breakdown

    def _generate_recommendation(self, comparison: dict[str, Any]) -> str:
        """Generate a recommendation based on comparison."""
        score_delta = comparison.get("score_delta", 0)
        findings_delta = comparison.get("findings_delta", 0)

        if score_delta > 5:
            return "memory_improved: Memory context improved review score significantly."
        if score_delta < -5:
            return (
                "memory_degraded: Memory context reduced review score. Investigate stale memories."
            )
        if findings_delta > 3:
            return "memory_reduced_findings: Memory context reduced noise (false positives)."
        if findings_delta < -3:
            return "memory_added_findings: Memory context surfaced additional issues."
        return "no_significant_difference: Memory context had minimal impact."
