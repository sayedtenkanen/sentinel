"""Simulation Engine — multi-turn synthetic test interactions (ADLC Test Phase).

Simulates sequential code reviews to verify agents behave correctly
across multiple rounds (e.g., findings decrease when code improves).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
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
class SimulationStep:
    content: str
    file_path: str = "simulation.py"
    expected_finding_range: tuple[int, int] | None = None
    expected_rule_ids: list[str] | None = None
    max_severity: Severity | None = None


@dataclass
class SimulationStepResult:
    step_index: int
    findings_count: int
    findings: list[Finding]
    duration_ms: float
    passed: bool
    rule_ids_found: set[str]
    rule_ids_missing: list[str]


@dataclass
class SimulationScenario:
    name: str
    steps: list[SimulationStep]

    def run(
        self,
        orchestrator: Orchestrator | None = None,
        agents: list | None = None,
        verbose: bool = True,
    ) -> SimulationResult:
        if orchestrator is None:
            orchestrator = Orchestrator(agents=agents or _default_agents())
        step_results: list[SimulationStepResult] = []

        for i, step in enumerate(self.steps):
            start = time.perf_counter()
            context = ReviewContext(
                files=[FileContext(path=step.file_path, content=step.content)],
            )
            report = orchestrator.review(context)
            elapsed = (time.perf_counter() - start) * 1000
            findings = report.all_findings
            found_ids = {f.rule_id for f in findings}
            missing_ids: list[str] = []
            passed = True

            if step.expected_rule_ids:
                missing_ids = [rid for rid in step.expected_rule_ids if rid not in found_ids]
                if missing_ids:
                    passed = False

            if step.expected_finding_range:
                lo, hi = step.expected_finding_range
                if not (lo <= len(findings) <= hi):
                    passed = False

            if step.max_severity:
                severity_order = list(Severity)
                max_idx = severity_order.index(step.max_severity)
                for f in findings:
                    if severity_order.index(f.severity) < max_idx:
                        passed = False
                        break

            step_results.append(
                SimulationStepResult(
                    step_index=i,
                    findings_count=len(findings),
                    findings=findings,
                    duration_ms=elapsed,
                    passed=passed,
                    rule_ids_found=found_ids,
                    rule_ids_missing=missing_ids,
                )
            )

        return SimulationResult(name=self.name, steps=step_results, verbose=verbose)


@dataclass
class SimulationResult:
    name: str
    steps: list[SimulationStepResult]
    verbose: bool = True

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.steps)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.steps if s.passed)

    def print(self) -> None:
        if not self.verbose:
            return
        status = "✅ PASS" if self.passed else "❌ FAIL"
        print(f"\n{status} | {self.name}")
        for s in self.steps:
            step_status = "✅" if s.passed else "❌"
            print(
                f"  Step {s.step_index}: {step_status} "
                f"{s.findings_count} findings ({s.duration_ms:.0f}ms)"
            )
            if not s.passed and s.rule_ids_missing:
                print(f"       Missing rules: {', '.join(s.rule_ids_missing)}")
            if s.findings:
                severity_counts = _count_by_severity(s.findings)
                parts = [f"{Severity(k).value}: {v}" for k, v in severity_counts.items() if v > 0]
                print(f"       Severity: {', '.join(parts)}")
        print()


def _default_agents() -> list:
    return [
        StaticAnalysisAgent(),
        SecurityAgent(),
        StyleAgent(),
        BestPracticesAgent(),
        DocumentationAgent(),
    ]


def _count_by_severity(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return counts


def _read_fixture(name: str) -> str:
    path = FIXTURES_DIR / name
    return path.read_text()


def _make_clean_code() -> str:
    return """\"\"\"Clean module with no issues.\"\"\"

from __future__ import annotations


def greet(name: str) -> str:
    \"\"\"Greet a user by name.\"\"\"
    return f"Hello, {name}!"
"""


def create_bad_to_good_scenario() -> SimulationScenario:
    bad = _read_fixture("bad_code.py")
    good = _read_fixture("good_code.py")
    return SimulationScenario(
        name="Bad to Good (findings decrease)",
        steps=[
            SimulationStep(
                content=bad,
                file_path=str(FIXTURES_DIR / "bad_code.py"),
                expected_finding_range=(10, 200),
            ),
            SimulationStep(
                content=good,
                file_path=str(FIXTURES_DIR / "good_code.py"),
                expected_finding_range=(0, 5),
            ),
        ],
    )


def create_no_regression_scenario() -> SimulationScenario:
    clean = _make_clean_code()
    dirty = clean + "\n\neval('dangerous')\n"
    return SimulationScenario(
        name="No regression (adding issue only adds new findings)",
        steps=[
            SimulationStep(
                content=clean,
                expected_finding_range=(0, 3),
            ),
            SimulationStep(
                content=dirty,
                file_path="simulation.py",
                expected_finding_range=(1, 10),
                expected_rule_ids=["SEC003"],
            ),
        ],
    )


def create_severity_improvement_scenario() -> SimulationScenario:
    bad_code = """\"\"\"Module with critical issues.\"\"\"
import subprocess
import pickle

def risky(data):
    eval(data)
    subprocess.call(data)
    pickle.loads(data)

user_input = request.GET["q"]
exec(user_input)
"""
    fixed_code = """\"\"\"Module with minor issues.\"\"\"

def risky(data: str) -> str:
    \"\"\"Process data safely.\"\"\"
    MAGIC = 42
    return data.strip()
"""

    return SimulationScenario(
        name="Severity improves (critical → low after fixes)",
        steps=[
            SimulationStep(
                content=bad_code,
                file_path="bad_sim.py",
                expected_finding_range=(5, 50),
            ),
            SimulationStep(
                content=fixed_code,
                file_path="fixed_sim.py",
                expected_finding_range=(0, 5),
            ),
        ],
    )


DEFAULT_SCENARIOS: list[Callable[[], SimulationScenario]] = [
    create_bad_to_good_scenario,
    create_no_regression_scenario,
    create_severity_improvement_scenario,
]


def run_simulations(verbose: bool = True) -> list[SimulationResult]:
    results = []
    for factory in DEFAULT_SCENARIOS:
        scenario = factory()
        result = scenario.run(verbose=verbose)
        result.print()
        results.append(result)
    return results


def print_summary(results: list[SimulationResult]) -> None:
    print(f"\n{'=' * 60}")
    print("  ADLC Simulation Engine Results")
    print(f"{'=' * 60}")
    total = 0
    passed = 0
    for r in results:
        total += r.total_steps
        passed += r.passed_steps
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.name}: {r.passed_steps}/{r.total_steps} steps passed")
    print(f"{'=' * 60}")
    print(f"  Score: {passed}/{total} steps ({passed / total * 100:.0f}%") if total else print(
        "  No scenarios"
    )
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    results = run_simulations()
    print_summary(results)
    sys.exit(0 if all(r.passed for r in results) else 1)
