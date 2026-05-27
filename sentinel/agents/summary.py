from __future__ import annotations

from ..core.base_agent import BaseAgent
from ..core.types import (
    FileContext,
    Finding,
    ReviewReport,
    Severity,
)


class SummaryAgent(BaseAgent):
    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="summary", enabled=enabled)

    def analyze(self, file: FileContext) -> list[Finding]:
        return []

    def summarize(self, report: ReviewReport) -> str:
        lines: list[str] = []
        findings = report.all_findings
        score = report.score

        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        high = [f for f in findings if f.severity == Severity.HIGH]
        medium = [f for f in findings if f.severity == Severity.MEDIUM]
        low = [f for f in findings if f.severity == Severity.LOW]
        info = [f for f in findings if f.severity == Severity.INFO]

        lines.append(f"## Review Summary (Score: {score}/100)")
        lines.append("")
        lines.append(f"**Files reviewed:** {len(report.files_reviewed)}")
        lines.append(f"**Findings total:** {len(findings)}")
        lines.append(f"**Duration:** {report.duration_ms:.0f}ms")
        lines.append("")
        lines.append("### Severity Breakdown")
        lines.append("")
        lines.append(f"- 🔴 Critical: {len(critical)}")
        lines.append(f"- 🟠 High: {len(high)}")
        lines.append(f"- 🟡 Medium: {len(medium)}")
        lines.append(f"- 🔵 Low: {len(low)}")
        lines.append(f"- ⚪ Info: {len(info)}")
        lines.append("")

        if score >= 90:
            rating = "Excellent"
        elif score >= 70:
            rating = "Good"
        elif score >= 50:
            rating = "Needs Improvement"
        else:
            rating = "Significant Issues Found"

        lines.append(f"**Verdict:** {rating}")
        lines.append("")

        return "\n".join(lines)
