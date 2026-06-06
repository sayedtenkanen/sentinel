"""Conflict resolution node for Sentinel Memory pipeline.

Resolves contradictory memories using priority-based rules:
- User preference vs. global rule: user wins
- Contradictory preferences: latest wins
- Memory vs. current reality: current wins
- Stale memory vs. fresh observation: fresh wins
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Memory, MemoryCandidate, MemoryType


@dataclass
class ConflictResolution:
    """Result of conflict resolution."""

    resolved: list[Memory] = field(default_factory=list)
    conflicts_found: int = 0
    resolutions_applied: int = 0


class MemoryConflictResolver:
    """Resolves conflicts between memories and candidates.

    Usage:
        resolver = MemoryConflictResolver()
        result = resolver.resolve(candidates, existing_memories)
    """

    @staticmethod
    def _normalize_timestamp(ts: str) -> datetime:
        """Parse an ISO timestamp and ensure it is timezone-aware (UTC)."""
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def resolve(
        self,
        candidates: list[MemoryCandidate],
        existing_memories: list[Memory],
    ) -> ConflictResolution:
        """Resolve conflicts between candidates and existing memories."""
        result = ConflictResolution()

        for candidate in candidates:
            conflicting = self._find_conflicts(candidate, existing_memories)

            if conflicting:
                result.conflicts_found += 1
                winner = self._resolve_conflict(candidate, conflicting)
                result.resolved.append(winner)
                result.resolutions_applied += 1
            else:
                result.resolved.append(
                    Memory(
                        type=candidate.type,
                        content=candidate.content,
                        confidence=candidate.confidence,
                        source=candidate.source,
                        tags=candidate.tags,
                    )
                )

        return result

    def _find_conflicts(self, candidate: MemoryCandidate, existing: list[Memory]) -> list[Memory]:
        """Find existing memories that conflict with the candidate."""
        conflicts: list[Memory] = []

        for memory in existing:
            if self._is_conflict(candidate, memory):
                conflicts.append(memory)

        return conflicts

    def _is_conflict(self, candidate: MemoryCandidate, memory: Memory) -> bool:
        """Check if a candidate conflicts with an existing memory."""
        if candidate.type == memory.type:
            return self._is_same_type_conflict(candidate, memory)

        return self._is_preference_vs_rule_conflict(candidate, memory)

    def _is_same_type_conflict(self, candidate: MemoryCandidate, memory: Memory) -> bool:
        """Check for conflicts between candidates and memories of the same type."""
        candidate_rule = candidate.content.get("rule_id")
        memory_rule = memory.content.get("rule_id")

        if candidate_rule and memory_rule and candidate_rule == memory_rule:
            candidate_pattern = candidate.content.get("feedback_pattern")
            memory_pattern = memory.content.get("feedback_pattern")
            if candidate_pattern and memory_pattern:
                return candidate_pattern != memory_pattern

        candidate_user = candidate.content.get("user")
        memory_user = memory.content.get("user")
        if candidate_user and memory_user and candidate_user == memory_user:
            candidate_pref = candidate.content.get("preferred_feedback")
            memory_pref = memory.content.get("preferred_feedback")
            if candidate_pref and memory_pref:
                return candidate_pref != memory_pref

        return False

    def _is_preference_vs_rule_conflict(self, candidate: MemoryCandidate, memory: Memory) -> bool:
        """Check if a preference candidate conflicts with an existing rule memory.

        A user preference about a rule (e.g., "SEC001 is correct") conflicts
        with an existing rule memory that has a different feedback pattern
        for the same rule.
        """
        if candidate.type != MemoryType.PREFERENCE or memory.type != MemoryType.RULE:
            return False

        candidate_rule = candidate.content.get("rule_id")
        memory_rule = memory.content.get("rule_id")

        if not candidate_rule or not memory_rule:
            return False

        if candidate_rule != memory_rule:
            return False

        candidate_pref = candidate.content.get("preferred_feedback")
        memory_pattern = memory.content.get("feedback_pattern")

        if candidate_pref and memory_pattern:
            return candidate_pref != memory_pattern

        return False

    def _resolve_conflict(self, candidate: MemoryCandidate, conflicting: list[Memory]) -> Memory:
        """Resolve conflict using priority rules.

        Rules:
        1. User preference vs. global rule: preference wins
        2. Latest observation wins (newer timestamp)
        3. Fresh observation beats stale memory (>30 days old)
        4. Higher confidence existing memory wins over low-confidence candidate
        """
        for existing in conflicting:
            if self._user_preference_wins(candidate, existing):
                return self._candidate_to_memory(candidate)

            if self._existing_wins_by_confidence(candidate, existing):
                return existing

            if self._latest_wins(candidate, existing):
                return self._candidate_to_memory(candidate)

            if self._fresh_wins(candidate, existing):
                return self._candidate_to_memory(candidate)

        return self._candidate_to_memory(candidate)

    def _user_preference_wins(self, candidate: MemoryCandidate, existing: Memory) -> bool:
        """User preference beats global rule."""
        return candidate.type == MemoryType.PREFERENCE and existing.type == MemoryType.RULE

    def _existing_wins_by_confidence(self, candidate: MemoryCandidate, existing: Memory) -> bool:
        """Existing memory wins if it has significantly higher confidence.

        An existing memory with confidence >= 0.9 and a candidate with
        confidence < 0.6 is kept, since the existing memory is well-established.
        """
        return existing.confidence >= 0.9 and candidate.confidence < 0.6

    def _latest_wins(self, candidate: MemoryCandidate, existing: Memory) -> bool:
        """Latest observation wins for same type."""
        try:
            candidate_time = self._normalize_timestamp(candidate.extracted_at)
            existing_time = self._normalize_timestamp(existing.created_at)
            return candidate_time > existing_time
        except (ValueError, TypeError):
            return True

    def _fresh_wins(self, candidate: MemoryCandidate, existing: Memory) -> bool:
        """Fresh observation beats stale memory."""
        try:
            candidate_time = self._normalize_timestamp(candidate.extracted_at)
            existing_time = self._normalize_timestamp(existing.last_used_at)
            age = (datetime.now(timezone.utc) - existing_time).days
            return age > 30 and candidate_time > existing_time
        except (ValueError, TypeError):
            return True

    def _candidate_to_memory(self, candidate: MemoryCandidate) -> Memory:
        """Convert a candidate to a memory."""
        return Memory(
            type=candidate.type,
            content=candidate.content,
            confidence=candidate.confidence,
            source=candidate.source,
            tags=candidate.tags,
        )
