"""Consolidation job for Sentinel Memory.

Periodic background task that runs the full memory pipeline:
extraction → validation → conflict resolution → synthesis → storage.
"""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field
from typing import Any

from .conflict import MemoryConflictResolver
from .extractor import ExtractionConfig, MemoryExtractor
from .models import FeedbackEvent, Memory, ReviewEvent
from .store import MemoryStore
from .synthesizer import MemorySynthesizer
from .temporal import TemporalManager
from .validator import MemoryValidator


@dataclass
class ConsolidationConfig:
    """Configuration for consolidation job."""

    interval_seconds: int = 3600  # 1 hour
    extraction_config: ExtractionConfig = field(default_factory=ExtractionConfig)
    enabled: bool = True


class ConsolidationJob:
    """Periodic background consolidation of memories.

    Usage:
        job = ConsolidationJob(store)
        job.start()
        # ... later ...
        job.stop()
    """

    def __init__(
        self,
        store: MemoryStore,
        config: ConsolidationConfig | None = None,
    ):
        self.store = store
        self.config = config or ConsolidationConfig()
        self._timer: threading.Timer | None = None
        self._running = False

        self.extractor = MemoryExtractor(self.config.extraction_config)
        self.validator = MemoryValidator()
        self.conflict_resolver = MemoryConflictResolver()
        self.synthesizer = MemorySynthesizer()
        self.temporal = TemporalManager()

    def start(self) -> None:
        """Start the periodic consolidation job."""
        if not self.config.enabled:
            return

        self._running = True
        self._schedule_next()

    def stop(self) -> None:
        """Stop the consolidation job."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def run_once(
        self,
        review_events: list[ReviewEvent] | None = None,
        feedback_events: list[FeedbackEvent] | None = None,
    ) -> dict[str, Any]:
        """Run consolidation once (manually or from timer)."""
        events = review_events or []
        feedbacks = feedback_events or []

        candidates = self.extractor.extract(events, feedbacks)

        existing = self.store.list_all()

        validated = self.validator.validate(candidates, existing)

        resolution = self.conflict_resolver.resolve(validated, existing)

        synthesized = self.synthesizer.synthesize(resolution.resolved)

        new_memories = self._filter_new_memories(synthesized, existing)

        for memory in new_memories:
            self.store.insert(memory)

        expired = self.temporal.find_expired(self.store.list_all())
        for mem in expired:
            self.store.delete(mem.id)

        return {
            "candidates_extracted": len(candidates),
            "validated": len(validated),
            "conflicts_found": resolution.conflicts_found,
            "resolutions_applied": resolution.resolutions_applied,
            "synthesized": len(synthesized),
            "new_stored": len(new_memories),
            "expired_removed": len(expired),
        }

    def _filter_new_memories(
        self, candidates: list[Memory], existing: list[Memory]
    ) -> list[Memory]:
        """Filter out candidates that already exist in the store."""
        existing_rules = {m.content.get("rule_id") for m in existing if m.content.get("rule_id")}

        new_memories: list[Memory] = []
        for candidate in candidates:
            if candidate.content.get("rule_id") in existing_rules:
                continue
            new_memories.append(candidate)

        return new_memories

    def _schedule_next(self) -> None:
        """Schedule the next consolidation run."""
        if not self._running:
            return

        self._timer = threading.Timer(self.config.interval_seconds, self._run_timer)
        self._timer.daemon = True
        self._timer.start()

    def _run_timer(self) -> None:
        """Run consolidation from timer and schedule next."""
        if not self._running:
            return

        with contextlib.suppress(Exception):
            self.run_once()

        self._schedule_next()
