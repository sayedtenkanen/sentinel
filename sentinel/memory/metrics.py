"""Metrics data models for Sentinel Memory evaluation.

Tracks run performance, memory quality, and user experience across
review sessions. Stores in SQLite for temporal queries.

Usage:
    from sentinel.memory.metrics import RunMetrics, MemoryMetrics, UserMetrics

    run = RunMetrics(
        run_id="run_20250101_120000",
        timestamp="2025-01-01T12:00:00",
        files_reviewed=5,
        findings_total=12,
        agent_latencies={"static_analysis": 45.2, "security": 32.1},
        token_cost=0.0,
        duration_ms=150.3,
        memory_retrieved=False,
        memory_count=0,
    )
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunMetrics:
    """Metrics for a single review run."""

    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    files_reviewed: int = 0
    findings_total: int = 0
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    findings_by_agent: dict[str, int] = field(default_factory=dict)
    agent_latencies: dict[str, float] = field(default_factory=dict)
    token_cost: float = 0.0
    duration_ms: float = 0.0
    memory_retrieved: bool = False
    memory_count: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryMetrics:
    """Metrics for memory system quality."""

    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    memory_precision: float = 0.0  # correct retrievals / total retrievals
    memory_recall: float = 0.0  # useful memories / total available
    contradiction_count: int = 0
    stale_memory_count: int = 0
    synthesis_count: int = 0
    memories_retrieved: int = 0
    memories_available: int = 0
    avg_memory_age_days: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserMetrics:
    """Metrics for user experience and feedback quality."""

    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    followup_reduction: float = 0.0  # fewer follow-up questions
    feedback_accuracy: float = 0.0  # correct / total feedback
    suppression_quality: float = 0.0  # suppressed false positives / total suppressions
    total_feedback: int = 0
    correct_feedback: int = 0
    total_suppressions: int = 0
    true_suppressions: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


_RUN_METRICS_DDL = """
    CREATE TABLE IF NOT EXISTS run_metrics (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT,
        files_reviewed INTEGER,
        findings_total INTEGER,
        findings_by_severity TEXT,
        findings_by_agent TEXT,
        agent_latencies TEXT,
        token_cost REAL,
        duration_ms REAL,
        memory_retrieved INTEGER,
        memory_count INTEGER,
        languages TEXT,
        metadata TEXT
    )
"""

_MEMORY_METRICS_DDL = """
    CREATE TABLE IF NOT EXISTS memory_metrics (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT,
        memory_precision REAL,
        memory_recall REAL,
        contradiction_count INTEGER,
        stale_memory_count INTEGER,
        synthesis_count INTEGER,
        memories_retrieved INTEGER,
        memories_available INTEGER,
        avg_memory_age_days REAL,
        metadata TEXT
    )
"""

_USER_METRICS_DDL = """
    CREATE TABLE IF NOT EXISTS user_metrics (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT,
        followup_reduction REAL,
        feedback_accuracy REAL,
        suppression_quality REAL,
        total_feedback INTEGER,
        correct_feedback INTEGER,
        total_suppressions INTEGER,
        true_suppressions INTEGER,
        metadata TEXT
    )
"""


class MetricsStore:
    """SQLite-backed metrics storage for temporal queries."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_RUN_METRICS_DDL)
            conn.execute(_MEMORY_METRICS_DDL)
            conn.execute(_USER_METRICS_DDL)

    def store_run(self, metrics: RunMetrics) -> None:
        """Store run metrics."""
        import json

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO run_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metrics.run_id,
                    metrics.timestamp,
                    metrics.files_reviewed,
                    metrics.findings_total,
                    json.dumps(metrics.findings_by_severity),
                    json.dumps(metrics.findings_by_agent),
                    json.dumps(metrics.agent_latencies),
                    metrics.token_cost,
                    metrics.duration_ms,
                    int(metrics.memory_retrieved),
                    metrics.memory_count,
                    json.dumps(metrics.languages),
                    json.dumps(metrics.metadata),
                ),
            )

    def store_memory(self, metrics: MemoryMetrics) -> None:
        """Store memory metrics."""
        import json

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memory_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metrics.run_id,
                    metrics.timestamp,
                    metrics.memory_precision,
                    metrics.memory_recall,
                    metrics.contradiction_count,
                    metrics.stale_memory_count,
                    metrics.synthesis_count,
                    metrics.memories_retrieved,
                    metrics.memories_available,
                    metrics.avg_memory_age_days,
                    json.dumps(metrics.metadata),
                ),
            )

    def store_user(self, metrics: UserMetrics) -> None:
        """Store user metrics."""
        import json

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO user_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metrics.run_id,
                    metrics.timestamp,
                    metrics.followup_reduction,
                    metrics.feedback_accuracy,
                    metrics.suppression_quality,
                    metrics.total_feedback,
                    metrics.correct_feedback,
                    metrics.total_suppressions,
                    metrics.true_suppressions,
                    json.dumps(metrics.metadata),
                ),
            )

    def query_runs(
        self,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[RunMetrics]:
        """Query run metrics with optional time range."""
        import json

        query = "SELECT * FROM run_metrics"
        params: list[Any] = []
        conditions: list[str] = []

        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [
            RunMetrics(
                run_id=row["run_id"],
                timestamp=row["timestamp"],
                files_reviewed=row["files_reviewed"],
                findings_total=row["findings_total"],
                findings_by_severity=json.loads(row["findings_by_severity"] or "{}"),
                findings_by_agent=json.loads(row["findings_by_agent"] or "{}"),
                agent_latencies=json.loads(row["agent_latencies"] or "{}"),
                token_cost=row["token_cost"],
                duration_ms=row["duration_ms"],
                memory_retrieved=bool(row["memory_retrieved"]),
                memory_count=row["memory_count"],
                languages=json.loads(row["languages"] or "{}"),
                metadata=json.loads(row["metadata"] or "{}"),
            )
            for row in rows
        ]

    def summary(self, since: str | None = None) -> dict[str, Any]:
        """Aggregate summary across all runs."""
        query = "SELECT * FROM run_metrics"
        params: list[Any] = []
        if since:
            query += " WHERE timestamp >= ?"
            params.append(since)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        if not rows:
            return {"total_runs": 0}

        total_files = sum(r["files_reviewed"] for r in rows)
        total_findings = sum(r["findings_total"] for r in rows)
        avg_duration = sum(r["duration_ms"] for r in rows) / len(rows)
        total_cost = sum(r["token_cost"] for r in rows)
        memory_runs = sum(1 for r in rows if r["memory_retrieved"])

        return {
            "total_runs": len(rows),
            "total_files_reviewed": total_files,
            "total_findings": total_findings,
            "avg_duration_ms": round(avg_duration, 2),
            "total_cost": round(total_cost, 4),
            "memory_usage_rate": round(memory_runs / len(rows), 2) if rows else 0,
            "period": {
                "since": rows[-1]["timestamp"] if rows else None,
                "until": rows[0]["timestamp"] if rows else None,
            },
        }
