from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewScope(Enum):
    FULL_FILE = "full_file"
    DIFF = "diff"
    PR = "pr"


@dataclass
class FileContext:
    path: str
    content: str
    language: str = ""
    diff: str | None = None
    is_new_file: bool = False


@dataclass
class Finding:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_name: str = ""
    severity: Severity = Severity.INFO
    file: str = ""
    line: int | None = None
    column: int | None = None
    message: str = ""
    suggestion: str = ""
    code_snippet: str | None = None
    rule_id: str = ""
    category: str = ""


@dataclass
class AgentResult:
    agent_name: str
    status: AgentStatus
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class TraceEvent:
    agent_name: str
    event: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ReviewReport:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    scope: ReviewScope = ReviewScope.FULL_FILE
    files_reviewed: list[FileContext] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    @property
    def all_findings(self) -> list[Finding]:
        findings = []
        for r in self.agent_results:
            findings.extend(r.findings)
        return sorted(findings, key=lambda f: list(Severity).index(f.severity))

    @property
    def score(self) -> int:
        if not self.all_findings:
            return 100
        severity_weights = {
            Severity.CRITICAL: 25,
            Severity.HIGH: 10,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
            Severity.INFO: 0,
        }
        deductions = sum(severity_weights.get(f.severity, 0) for f in self.all_findings)
        return max(0, min(100, 100 - deductions))
