"""Unit tests for the risk summary agent."""

import unittest

from sentinel.agents.risk_summary import assess_risk, format_risk_summary
from sentinel.core.types import (
    AgentResult,
    AgentStatus,
    Finding,
    ReviewReport,
    Severity,
)


def _report_with_findings(findings: list[Finding]) -> ReviewReport:
    report = ReviewReport()
    report.agent_results.append(
        AgentResult(agent_name="test", status=AgentStatus.COMPLETED, findings=findings)
    )
    return report


class TestAssessRisk(unittest.TestCase):
    def test_no_findings(self):
        report = ReviewReport()
        self.assertEqual(assess_risk(report), [])

    def test_single_low_finding(self):
        findings = [
            Finding(file="a.py", severity=Severity.LOW, rule_id="ST001"),
        ]
        risks = assess_risk(_report_with_findings(findings))
        self.assertEqual(len(risks), 0)

    def test_risk_concentration_critical(self):
        findings = [
            Finding(file="a.py", severity=Severity.CRITICAL, rule_id=f"SEC{i:03d}")
            for i in range(5)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertIn("RSK001", rule_ids)

    def test_risk_concentration_high(self):
        findings = [
            Finding(file="a.py", severity=Severity.HIGH, rule_id=f"SEC{i:03d}") for i in range(3)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertIn("RSK002", rule_ids)

    def test_cross_cutting_security(self):
        findings = [
            Finding(
                file=f"app{i}.py", severity=Severity.CRITICAL, rule_id="SEC001", category="security"
            )
            for i in range(3)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertIn("RSK003", rule_ids)

    def test_cross_cutting_security_below_threshold(self):
        findings = [
            Finding(
                file=f"app{i}.py", severity=Severity.CRITICAL, rule_id="SEC001", category="security"
            )
            for i in range(2)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertNotIn("RSK003", rule_ids)

    def test_architecture_cycles_detected(self):
        findings = [
            Finding(file="a.py", severity=Severity.HIGH, rule_id="ARC001", category="architecture"),
            Finding(file="b.py", severity=Severity.HIGH, rule_id="ARC001", category="architecture"),
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertIn("RSK004", rule_ids)

    def test_overall_risk(self):
        findings = [
            Finding(file=f"f{i}.py", severity=Severity.CRITICAL, rule_id=f"SEC{i:03d}")
            for i in range(10)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertIn("RSK005", rule_ids)

    def test_overall_risk_below_threshold(self):
        findings = [
            Finding(file=f"f{i}.py", severity=Severity.CRITICAL, rule_id=f"SEC{i:03d}")
            for i in range(5)
        ]
        risks = assess_risk(_report_with_findings(findings))
        rule_ids = [r["rule_id"] for r in risks]
        self.assertNotIn("RSK005", rule_ids)

    def test_mixed_findings(self):
        findings = [
            Finding(
                file="crunch.py", severity=Severity.CRITICAL, rule_id="SEC001", category="security"
            ),
            Finding(
                file="crunch.py", severity=Severity.HIGH, rule_id="SEC002", category="security"
            ),
            Finding(
                file="crunch.py", severity=Severity.HIGH, rule_id="SEC003", category="security"
            ),
            Finding(
                file="crunch.py", severity=Severity.HIGH, rule_id="SEC004", category="security"
            ),
            Finding(
                file="crunch.py", severity=Severity.HIGH, rule_id="SEC005", category="security"
            ),
        ]
        risks = assess_risk(_report_with_findings(findings))
        self.assertGreater(len(risks), 0)


class TestFormatRiskSummary(unittest.TestCase):
    def test_empty(self):
        result = format_risk_summary([])
        self.assertIn("No significant risks", result)

    def test_single_risk(self):
        items = [
            {
                "type": "risk_concentration",
                "severity": "critical",
                "file": "app.py",
                "message": "Risk concentration: 5 findings",
                "suggestion": "Prioritize review",
                "count": 5,
                "total": 10,
                "rule_id": "RSK001",
            }
        ]
        result = format_risk_summary(items)
        self.assertIn("RSK001", result)
        self.assertIn("Risk concentration", result)
        self.assertIn("Prioritize review", result)

    def test_multiple_risks(self):
        items = [
            {
                "rule_id": "RSK001",
                "severity": "critical",
                "message": "First",
                "suggestion": "Fix A",
                "type": "risk_concentration",
                "file": "a.py",
                "count": 5,
                "total": 5,
            },
            {
                "rule_id": "RSK002",
                "severity": "high",
                "message": "Second",
                "suggestion": "Fix B",
                "type": "risk_concentration",
                "file": "b.py",
                "count": 3,
                "total": 3,
            },
        ]
        result = format_risk_summary(items)
        self.assertIn("RSK001", result)
        self.assertIn("RSK002", result)
        self.assertIn("Total risks flagged: 2", result)


if __name__ == "__main__":
    unittest.main()
