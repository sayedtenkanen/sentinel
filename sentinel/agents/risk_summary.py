"""PR-level risk summary — cross-file risk assessment and aggregation.

Runs after all other agents to produce a holistic risk picture:
- Risk concentration per file/module
- Severity distribution across the project
- Cross-file risk patterns
- Remediation priority
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..core.types import ReviewReport, Severity


def assess_risk(report: ReviewReport) -> list[dict]:
    """Analyze a ReviewReport and return risk findings.

    report: The full review report after all agents have run.
    """
    findings = report.all_findings
    if not findings:
        return []

    risk_items: list[dict] = []

    file_findings: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        file_findings[f.file].append(
            {
                "severity": f.severity,
                "rule_id": f.rule_id,
                "message": f.message,
                "agent": f.agent_name,
            }
        )

    for file_path, file_fs in file_findings.items():
        severity_counts = Counter(f["severity"].value for f in file_fs)
        total = len(file_fs)
        high_crit = severity_counts.get("critical", 0) + severity_counts.get("high", 0)

        if high_crit >= 5:
            risk_items.append(
                {
                    "type": "risk_concentration",
                    "severity": "critical",
                    "file": file_path,
                    "message": (
                        f"Risk concentration: {high_crit} high/critical findings in {file_path}"
                    ),
                    "suggestion": "Prioritize review of this file before deployment",
                    "count": high_crit,
                    "total": total,
                    "rule_id": "RSK001",
                }
            )

        elif high_crit >= 3:
            risk_items.append(
                {
                    "type": "risk_concentration",
                    "severity": "high",
                    "file": file_path,
                    "message": (
                        f"Moderate risk concentration: {high_crit} high/critical findings "
                        f"in {file_path}"
                    ),
                    "suggestion": "Review high-severity findings in this file",
                    "count": high_crit,
                    "total": total,
                    "rule_id": "RSK002",
                }
            )

    security_files = {
        f.file
        for f in findings
        if f.category == "security" and f.severity in (Severity.CRITICAL, Severity.HIGH)
    }
    if len(security_files) >= 3:
        risk_items.append(
            {
                "type": "cross_cutting",
                "severity": "high",
                "file": " (multiple files)",
                "message": (
                    f"Cross-cutting security issues: {len(security_files)} files "
                    f"with high/critical security findings"
                ),
                "suggestion": "Audit security posture across the entire project",
                "count": len(security_files),
                "rule_id": "RSK003",
            }
        )

    architecture_findings = [f for f in findings if f.category == "architecture"]
    if architecture_findings:
        cycle_count = sum(1 for f in architecture_findings if f.rule_id == "ARC001")
        if cycle_count >= 2:
            risk_items.append(
                {
                    "type": "architecture",
                    "severity": "high",
                    "file": " (project-wide)",
                    "message": (
                        f"Architectural risk: {cycle_count} circular dependencies detected"
                    ),
                    "suggestion": "Restructure imports to eliminate circular dependencies",
                    "count": cycle_count,
                    "rule_id": "RSK004",
                }
            )

    total_critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    if total_critical >= 10:
        risk_items.append(
            {
                "type": "overall",
                "severity": "critical",
                "file": " (project-wide)",
                "message": (
                    f"High overall risk: {total_critical} critical findings across the project"
                ),
                "suggestion": "Block deployment until critical issues are resolved",
                "count": total_critical,
                "rule_id": "RSK005",
            }
        )

    return _sort_risk_items(risk_items)


def _sort_risk_items(items: list[dict]) -> list[dict]:
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return sorted(items, key=lambda r: severity_order.get(r["severity"], 99))


def format_risk_summary(risk_items: list[dict]) -> str:
    if not risk_items:
        return "No significant risks detected."
    lines = ["## PR-level Risk Summary\n"]
    for item in risk_items:
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(item["severity"], "⚪")
        lines.append(f"{emoji} **[{item['rule_id']}]** {item['message']}")
        lines.append(f"   *Suggestion:* {item['suggestion']}")
        lines.append("")
    lines.append(f"**Total risks flagged: {len(risk_items)}**")
    return "\n".join(lines)
