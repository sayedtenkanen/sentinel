"""Validation node for Sentinel Memory pipeline.

Validates memory candidates by checking confidence thresholds,
sample size, freshness, and consistency with existing memories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import Memory, MemoryCandidate


@dataclass
class ValidationConfig:
    """Configuration for memory validation."""

    min_confidence: float = 0.6
    max_age_days: int = 30
    min_sample_size: int = 3


class MemoryValidator:
    """Validates memory candidates before they become memories.

    Usage:
        validator = MemoryValidator()
        validated = validator.validate(candidates, existing_memories)
    """

    def __init__(self, config: ValidationConfig | None = None):
        self.config = config or ValidationConfig()

    def validate(
        self,
        candidates: list[MemoryCandidate],
        existing_memories: list[Memory] | None = None,
    ) -> list[MemoryCandidate]:
        """Validate candidates against thresholds and existing memories."""
        existing = existing_memories or []
        validated: list[MemoryCandidate] = []

        for candidate in candidates:
            if self._is_valid(candidate, existing):
                validated.append(candidate)

        return validated

    def _is_valid(self, candidate: MemoryCandidate, _existing_memories: list[Memory]) -> bool:
        """Check if a single candidate is valid."""
        if not self._check_confidence(candidate):
            return False

        if not self._check_sample_size(candidate):
            return False

        return self._check_freshness(candidate)

    def _check_confidence(self, candidate: MemoryCandidate) -> bool:
        """Check if candidate meets minimum confidence threshold."""
        return candidate.confidence >= self.config.min_confidence

    def _check_sample_size(self, candidate: MemoryCandidate) -> bool:
        """Check if candidate has sufficient evidence."""
        content = candidate.content
        if "sample_size" in content:
            return content["sample_size"] >= self.config.min_sample_size
        if "total_feedbacks" in content:
            return content["total_feedbacks"] >= self.config.min_sample_size
        return len(candidate.evidence) >= self.config.min_sample_size

    def _check_freshness(self, candidate: MemoryCandidate) -> bool:
        """Check if candidate was extracted recently enough."""
        try:
            extracted_at = datetime.fromisoformat(candidate.extracted_at)
            max_age = timedelta(days=self.config.max_age_days)
            return (datetime.now(timezone.utc) - extracted_at) <= max_age
        except (ValueError, TypeError):
            return True

    def validate_against_existing(
        self,
        candidate: MemoryCandidate,
        existing_memories: list[Memory],
    ) -> tuple[bool, str]:
        """Validate candidate against existing memories.

        Returns (is_valid, reason) tuple.
        """
        for memory in existing_memories:
            if self._contradicts(candidate, memory):
                return False, f"Contradicts existing memory {memory.id}"

        return True, "OK"

    def _contradicts(self, candidate: MemoryCandidate, memory: Memory) -> bool:
        """Check if candidate contradicts an existing memory."""
        if candidate.type != memory.type:
            return False

        candidate_rule = candidate.content.get("rule_id")
        memory_rule = memory.content.get("rule_id")

        if candidate_rule and memory_rule and candidate_rule == memory_rule:
            candidate_pattern = candidate.content.get("feedback_pattern")
            memory_pattern = memory.content.get("feedback_pattern")
            if candidate_pattern and memory_pattern:
                return candidate_pattern != memory_pattern

        return False
