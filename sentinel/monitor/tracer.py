from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.types import TraceEvent


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
    ) -> None:
        self.enabled = enabled
        self._events: list[TraceEvent] = []
        self._metrics: list[MetricPoint] = []
        self.log_dir = log_dir

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
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def flush(self) -> None:
        if not self.log_dir:
            return
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.log_dir, f"trace_{timestamp}.json")
        self.export_trace(path)
