"""Markdown and JSON report generators."""

from __future__ import annotations

import json

from ..core.types import Finding, ReviewReport, Severity


def format_finding(finding: Finding) -> str:
    location = finding.file
    if finding.line:
        location += f":{finding.line}"
        if finding.column:
            location += f":{finding.column}"

    severity_tag = {
        Severity.CRITICAL: "🔴 CRITICAL",
        Severity.HIGH: "🟠 HIGH",
        Severity.MEDIUM: "🟡 MEDIUM",
        Severity.LOW: "🔵 LOW",
        Severity.INFO: "⚪ INFO",
    }.get(finding.severity, "INFO")

    parts = [
        f"### [{severity_tag}] {finding.message}",
        f"**Location:** `{location}`",
        f"**Rule:** `{finding.rule_id}` | **Agent:** `{finding.agent_name}`",
    ]

    if finding.suggestion:
        parts.append(f"\n**Suggestion:** {finding.suggestion}")

    if finding.code_snippet:
        parts.append(f"\n```\n{finding.code_snippet}\n```")

    return "\n\n".join(parts)


def _header_section(report: ReviewReport) -> str:
    sections = [
        "# Code Review Report",
        "",
        f"**ID:** `{report.id}`",
        f"**Scope:** `{report.scope.value}`",
        f"**Files:** {len(report.files_reviewed)}",
        f"**Duration:** {report.duration_ms:.0f}ms",
        f"**Score:** {report.score}/100",
        "",
        "---",
        "",
    ]
    return "\n".join(sections)


def _findings_sections(report: ReviewReport) -> str:
    sections = ["## Detailed Findings", ""]
    by_severity = {
        Severity.CRITICAL: [],
        Severity.HIGH: [],
        Severity.MEDIUM: [],
        Severity.LOW: [],
        Severity.INFO: [],
    }
    for finding in report.all_findings:
        by_severity[finding.severity].append(finding)

    for severity in [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.INFO,
    ]:
        findings = by_severity[severity]
        if not findings:
            continue
        sections.append(f"### {severity.value.upper()} ({len(findings)})")
        sections.append("")
        for finding in findings:
            sections.append(format_finding(finding))
            sections.append("")
        sections.append("---")
        sections.append("")
    return "\n".join(sections)


def to_markdown(report: ReviewReport, summary_text: str) -> str:
    if not report.all_findings:
        return "\n".join(
            [
                _header_section(report),
                summary_text,
                "",
                "---",
                "",
                "✅ No issues found. Great work!",
            ]
        )

    return "\n".join(
        [
            _header_section(report),
            summary_text,
            "",
            "---",
            "",
            _findings_sections(report),
        ]
    )


def to_json(report: ReviewReport, summary_text: str) -> str:
    return json.dumps(
        {
            "id": report.id,
            "scope": report.scope.value,
            "score": report.score,
            "duration_ms": report.duration_ms,
            "files_reviewed": len(report.files_reviewed),
            "summary": summary_text,
            "findings": [
                {
                    "id": f.id,
                    "agent": f.agent_name,
                    "severity": f.severity.value,
                    "file": f.file,
                    "line": f.line,
                    "column": f.column,
                    "message": f.message,
                    "suggestion": f.suggestion,
                    "rule_id": f.rule_id,
                    "category": f.category,
                }
                for f in report.all_findings
            ],
            "agent_results": [
                {
                    "agent": r.agent_name,
                    "status": r.status.value,
                    "findings": len(r.findings),
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in report.agent_results
            ],
        },
        indent=2,
    )
