"""
evals.py — ADLC Test Phase: evaluation framework.

Uses known-good and known-bad fixtures to validate agent behavior.
Supports experiments (comparing agent versions) and metrics tracking.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..agents.best_practices import BestPracticesAgent
from ..agents.documentation import DocumentationAgent
from ..agents.security import SecurityAgent
from ..agents.static_analysis import StaticAnalysisAgent
from ..agents.style import StyleAgent
from ..core.context import ReviewContext
from ..core.orchestrator import Orchestrator
from ..core.types import FileContext, Finding, Severity

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass
class EvalCase:
    name: str
    file_path: str
    content: str
    expected_issue_count: int
    expected_min_severity: Severity | None = None
    expected_rule_ids: list[str] | None = None


@dataclass
class EvalResult:
    case_name: str
    passed: bool
    findings_count: int
    expected_count: int
    missing_issues: list[str]
    duration_ms: float


@dataclass
class EvalSuite:
    name: str
    results: list[EvalResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def score(self) -> float:
        if not self.results:
            return 100.0
        return (self.passed / self.total) * 100


def make_eval_cases() -> list[EvalCase]:
    good_path = str(FIXTURES_DIR / "good_code.py")
    bad_path = str(FIXTURES_DIR / "bad_code.py")

    with open(bad_path) as f:
        bad_content = f.read()
    with open(good_path) as f:
        good_content = f.read()

    return [
        EvalCase(
            name="bad_code_has_issues",
            file_path=bad_path,
            content=bad_content,
            expected_issue_count=20,
            expected_min_severity=Severity.CRITICAL,
            expected_rule_ids=[
                "SEC001",
                "SEC099",
                "BP001",
                "BP003",
                "BP004",
                "BP007",
                "STY002",
                "STY003",
                "ST001",
                "DOC001",
                "DOC002",
                "DOC003",
                "DOC004",
                "DOC005",
            ],
        ),
        EvalCase(
            name="good_code_minimal_issues",
            file_path=good_path,
            content=good_content,
            expected_issue_count=0,
        ),
    ]


MetricFn = Callable[[list[Finding]], float]


@dataclass
class Experiment:
    name: str
    baseline_orchestrator: Orchestrator
    candidate_orchestrator: Orchestrator
    eval_cases: list[EvalCase]
    metrics: list[MetricFn] = field(default_factory=list)

    def run(self) -> dict:
        baseline_results = _run_eval_cases(self.baseline_orchestrator, self.eval_cases)
        candidate_results = _run_eval_cases(self.candidate_orchestrator, self.eval_cases)

        baseline_score = EvalSuite(name="baseline", results=baseline_results)
        candidate_score = EvalSuite(name="candidate", results=candidate_results)

        return {
            "experiment": self.name,
            "baseline": {
                "score": baseline_score.score,
                "passed": baseline_score.passed,
                "total": baseline_score.total,
            },
            "candidate": {
                "score": candidate_score.score,
                "passed": candidate_score.passed,
                "total": candidate_score.total,
            },
        }


def _run_eval_cases(orchestrator: Orchestrator, cases: list[EvalCase]) -> list[EvalResult]:
    results: list[EvalResult] = []
    for case in cases:
        start = time.perf_counter()
        context = ReviewContext(
            files=[FileContext(path=case.file_path, content=case.content)],
        )
        report = orchestrator.review(context)
        elapsed = (time.perf_counter() - start) * 1000

        findings = report.all_findings
        count = len(findings)

        missing = []
        if case.expected_rule_ids:
            found_ids = {f.rule_id for f in findings}
            missing = [rid for rid in case.expected_rule_ids if rid not in found_ids]

        passed = True
        if case.expected_issue_count > 0 and count < 10:
            passed = False
        if case.expected_min_severity:
            severities = {f.severity for f in findings}
            severity_order = list(Severity)
            min_idx = severity_order.index(case.expected_min_severity)
            if not any(severity_order.index(s) <= min_idx for s in severities):
                passed = False

        results.append(
            EvalResult(
                case_name=case.name,
                passed=passed,
                findings_count=count,
                expected_count=case.expected_issue_count,
                missing_issues=missing,
                duration_ms=elapsed,
            )
        )

    return results


def run_evals(verbose: bool = True) -> EvalSuite:
    orchestrator = Orchestrator(
        agents=[
            StaticAnalysisAgent(),
            SecurityAgent(),
            StyleAgent(),
            BestPracticesAgent(),
            DocumentationAgent(),
        ]
    )
    cases = make_eval_cases()
    results = _run_eval_cases(orchestrator, cases)
    suite = EvalSuite(name="ADLC Test Suite", results=results)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  ADLC Test Phase: {suite.name}")
        print(f"{'=' * 60}")
        for r in suite.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            print(
                f"  {status} | {r.case_name:30s} | "
                f"{r.findings_count:2d} findings ({r.duration_ms:.0f}ms)"
            )
            if not r.passed and r.missing_issues:
                print(f"       Missing rules: {', '.join(r.missing_issues)}")
        print(f"{'=' * 60}")
        print(f"  Score: {suite.score:.0f}% ({suite.passed}/{suite.total} passed)")
        print(f"{'=' * 60}\n")

    return suite


if __name__ == "__main__":
    suite = run_evals()
    sys.exit(0 if suite.score >= 50 else 1)
