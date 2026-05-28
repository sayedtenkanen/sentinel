"""Cost Governance — track and cap per-review cost (ADLC Govern phase).

Supports cost tracking for both static analysis (free) and LLM-based agents
(charged per duration). Default cost rates can be overridden per agent.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

DEFAULT_COST_RATES: dict[str, float] = {
    "static-analysis": 0.0,
    "security": 0.0,
    "style": 0.0,
    "best-practices": 0.0,
    "documentation": 0.0,
}


@dataclass
class CostEntry:
    agent_name: str
    duration_ms: float
    rate_per_ms: float
    cost: float

    def __post_init__(self) -> None:
        self.cost = self.duration_ms * self.rate_per_ms


@dataclass
class CostReport:
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return round(sum(e.cost for e in self.entries), 6)

    @property
    def total_duration_ms(self) -> float:
        return round(sum(e.duration_ms for e in self.entries), 2)

    def add(
        self, agent_name: str, duration_ms: float, rate_per_ms: float | None = None
    ) -> CostEntry:
        rate = rate_per_ms if rate_per_ms is not None else DEFAULT_COST_RATES.get(agent_name, 0.0)
        entry = CostEntry(
            agent_name=agent_name,
            duration_ms=duration_ms,
            rate_per_ms=rate,
            cost=duration_ms * rate,
        )
        self.entries.append(entry)
        return entry

    def to_dict(self) -> dict:
        return {
            "total_cost": self.total_cost,
            "total_duration_ms": self.total_duration_ms,
            "entries": [
                {
                    "agent": e.agent_name,
                    "duration_ms": e.duration_ms,
                    "rate_per_ms": e.rate_per_ms,
                    "cost": e.cost,
                }
                for e in self.entries
            ],
        }

    def summary_line(self) -> str:
        return f"Cost: ${self.total_cost:.6f} (duration: {self.total_duration_ms:.0f}ms)"


class CostTracker:
    def __init__(
        self,
        cost_cap: float | None = None,
        custom_rates: dict[str, float] | None = None,
        enabled: bool = True,
    ) -> None:
        self.cost_cap = cost_cap
        self.enabled = enabled
        self._rates: dict[str, float] = dict(DEFAULT_COST_RATES)
        if custom_rates:
            self._rates.update(custom_rates)
        self._report = CostReport()
        self._lock = threading.RLock()

    @property
    def report(self) -> CostReport:
        with self._lock:
            return self._report

    @property
    def total_cost(self) -> float:
        with self._lock:
            return self._report.total_cost

    @property
    def cap_exceeded(self) -> bool:
        with self._lock:
            if self.cost_cap is None:
                return False
            return self.total_cost > self.cost_cap

    def track(
        self, agent_name: str, duration_ms: float, rate_per_ms: float | None = None
    ) -> CostEntry:
        with self._lock:
            if not self.enabled:
                entry = CostEntry(agent_name=agent_name, duration_ms=0, rate_per_ms=0, cost=0)
                self._report.entries.append(entry)
                return entry
            rate = rate_per_ms if rate_per_ms is not None else self._rates.get(agent_name, 0.0)
            entry = self._report.add(agent_name, duration_ms, rate)
            return entry

    def reset(self) -> None:
        with self._lock:
            self._report = CostReport()
