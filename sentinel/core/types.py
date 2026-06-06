"""Shared data models for findings, reports, and trace events."""

from __future__ import annotations

import math
import uuid
from collections import Counter
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


class FeedbackType(Enum):
    HUMAN = "human"
    LLM = "llm"


class FeedbackRating(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNSURE = "unsure"


@dataclass
class Feedback:
    finding_id: str
    trace_file: str = ""
    feedback_type: FeedbackType = FeedbackType.HUMAN
    rating: FeedbackRating = FeedbackRating.UNSURE
    comment: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
    reviewed: bool = False


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
        severity_multipliers = {
            Severity.CRITICAL: 12,
            Severity.HIGH: 6,
            Severity.MEDIUM: 3,
            Severity.LOW: 0.5,
            Severity.INFO: 0,
        }
        counts = Counter(f.severity for f in self.all_findings)
        deductions = 0.0
        for sev, count in counts.items():
            multiplier = severity_multipliers.get(sev, 0)
            if multiplier > 0 and count > 0:
                deductions += multiplier * (1 + math.log(count))
        return max(0, min(100, round(100 - deductions)))
