"""Tracer for capturing trace events and metrics (Monitor phase)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.types import Feedback, TraceEvent


@dataclass
class MetricPoint:
    name: str
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Tracer:
    def __init__(
        self,
        log_dir: str | None = None,
        enabled: bool = True,
        feedback_dir: str | None = None,
    ) -> None:
        self.enabled = enabled
        self._events: list[TraceEvent] = []
        self._metrics: list[MetricPoint] = []
        self._feedbacks: list[Feedback] = []
        self.log_dir = log_dir
        self.feedback_dir = feedback_dir or log_dir

    def trace(self, event: TraceEvent) -> None:
        if not self.enabled:
            return
        self._events.append(event)

    def metric(self, name: str, value: float, labels: dict | None = None) -> None:
        if not self.enabled:
            return
        self._metrics.append(
            MetricPoint(
                name=name,
                value=value,
                labels=labels or {},
            )
        )

    def store_feedback(self, feedback: Feedback) -> None:
        if not self.enabled:
            return
        self._feedbacks.append(feedback)

    def get_feedback(self) -> list[Feedback]:
        return list(self._feedbacks)

    def get_events(self) -> list[TraceEvent]:
        return list(self._events)

    def get_metrics(self) -> list[MetricPoint]:
        return list(self._metrics)

    def summary(self) -> dict:
        agent_durations: dict[str, float] = {}
        agent_errors: list[str] = []

        for event in self._events:
            if event.event == "run.completed":
                agent_durations[event.agent_name] = (
                    agent_durations.get(event.agent_name, 0) + event.duration_ms
                )
            elif event.event == "run.failed":
                agent_errors.append(f"{event.agent_name}: {event.metadata.get('error', 'unknown')}")

        return {
            "total_events": len(self._events),
            "total_metrics": len(self._metrics),
            "agent_durations_ms": agent_durations,
            "errors": agent_errors,
        }

    def export_trace(self, path: str) -> None:
        data = {
            "events": [
                {
                    "agent": e.agent_name,
                    "event": e.event,
                    "timestamp": e.timestamp.isoformat(),
                    "duration_ms": e.duration_ms,
                    "metadata": e.metadata,
                }
                for e in self._events
            ],
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "labels": m.labels,
                }
                for m in self._metrics
            ],
            "feedbacks": [
                {
                    "finding_id": f.finding_id,
                    "trace_file": f.trace_file,
                    "feedback_type": f.feedback_type.value,
                    "rating": f.rating.value,
                    "comment": f.comment,
                    "timestamp": f.timestamp.isoformat(),
                }
                for f in self._feedbacks
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def export_feedback(self, trace_filename: str) -> str | None:
        if not self._feedbacks:
            return None
        if not self.feedback_dir:
            return None
        os.makedirs(self.feedback_dir, exist_ok=True)
        path = os.path.join(self.feedback_dir, f"feedback_{trace_filename}")
        data = [
            {
                "finding_id": f.finding_id,
                "trace_file": f.trace_file,
                "feedback_type": f.feedback_type.value,
                "rating": f.rating.value,
                "comment": f.comment,
                "timestamp": f.timestamp.isoformat(),
            }
            for f in self._feedbacks
        ]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def flush(self) -> None:
        if not self.log_dir:
            return
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.log_dir, f"trace_{timestamp}.json")
        self.export_trace(path)
        if self._feedbacks:
            self.export_feedback(f"trace_{timestamp}.json")
