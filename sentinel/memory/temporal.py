"""Temporal logic for Sentinel Memory.

Handles memory aging, decay, expiration, and archival based on
memory type and configured half-lives.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import Memory, MemoryType


@dataclass
class TemporalConfig:
    """Configuration for temporal logic."""

    preference_half_life_days: int | None = None  # Never expires
    context_half_life_days: int = 90
    pattern_half_life_days: int = 30
    temporal_half_life_days: int = 14

    preference_archive_days: int | None = None  # Never archives
    context_archive_days: int = 180
    pattern_archive_days: int = 60
    temporal_archive_days: int = 30


class TemporalManager:
    """Manages memory aging, decay, and expiration.

    Usage:
        temporal = TemporalManager()
        expired = temporal.find_expired(memories)
        active = temporal.filter_active(memories)
    """

    def __init__(self, config: TemporalConfig | None = None):
        self.config = config or TemporalConfig()

    @staticmethod
    def _normalize_timestamp(ts: str) -> datetime:
        """Parse an ISO timestamp and ensure it is timezone-aware (UTC).

        Handles:
        - Timezone-aware strings (e.g., '2025-01-01T00:00:00+00:00')
        - Naive strings (e.g., '2025-01-01T00:00:00') — assumed UTC
        - 'Z' suffix (e.g., '2025-01-01T00:00:00Z') — treated as UTC
        """
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def find_expired(self, memories: list[Memory]) -> list[Memory]:
        """Find memories that have expired based on their type."""
        now = datetime.now(timezone.utc)
        expired: list[Memory] = []

        for mem in memories:
            if self._is_expired(mem, now):
                expired.append(mem)

        return expired

    def filter_active(self, memories: list[Memory]) -> list[Memory]:
        """Return only active (non-expired) memories."""
        now = datetime.now(timezone.utc)
        return [mem for mem in memories if not self._is_expired(mem, now)]

    def find_archivable(self, memories: list[Memory]) -> list[Memory]:
        """Find memories that should be archived."""
        now = datetime.now(timezone.utc)
        archivable: list[Memory] = []

        for mem in memories:
            if self._is_archivable(mem, now):
                archivable.append(mem)

        return archivable

    def calculate_decay(self, memory: Memory) -> float:
        """Calculate decay factor for a memory (0.0 to 1.0).

        Returns 1.0 for fresh memories, approaching 0.0 as they age.
        """
        half_life = self._get_half_life_days(memory.type)
        if half_life is None:
            return 1.0

        try:
            created = self._normalize_timestamp(memory.created_at)
            age_days = (datetime.now(timezone.utc) - created).days
            decay = 0.5 ** (age_days / half_life)
            return max(0.0, min(1.0, decay))
        except (ValueError, TypeError):
            return 1.0

    def apply_decay_to_confidence(self, memory: Memory) -> float:
        """Apply temporal decay to a memory's confidence score."""
        decay = self.calculate_decay(memory)
        return memory.confidence * decay

    def get_age_days(self, memory: Memory) -> int:
        """Get the age of a memory in days."""
        try:
            created = self._normalize_timestamp(memory.created_at)
            return (datetime.now(timezone.utc) - created).days
        except (ValueError, TypeError):
            return 0

    def _is_expired(self, memory: Memory, now: datetime) -> bool:
        """Check if a memory has expired."""
        if memory.expires_at:
            try:
                expires = self._normalize_timestamp(memory.expires_at)
                return now > expires
            except (ValueError, TypeError):
                return False

        archive_days = self._get_archive_days(memory.type)
        if archive_days is None:
            return False

        try:
            created = self._normalize_timestamp(memory.created_at)
            age = (now - created).days
            return age > archive_days
        except (ValueError, TypeError):
            return False

    def _is_archivable(self, memory: Memory, now: datetime) -> bool:
        """Check if a memory should be archived."""
        archive_days = self._get_archive_days(memory.type)
        if archive_days is None:
            return False

        try:
            created = self._normalize_timestamp(memory.created_at)
            age = (now - created).days
            return age > archive_days * 0.8
        except (ValueError, TypeError):
            return False

    def _get_half_life_days(self, mem_type: MemoryType) -> int | None:
        """Get half-life for a memory type."""
        if mem_type == MemoryType.PREFERENCE:
            return self.config.preference_half_life_days
        if mem_type == MemoryType.CONTEXT:
            return self.config.context_half_life_days
        if mem_type == MemoryType.RULE:
            return self.config.pattern_half_life_days
        if mem_type == MemoryType.TEMPORAL:
            return self.config.temporal_half_life_days
        return 30

    def _get_archive_days(self, mem_type: MemoryType) -> int | None:
        """Get archive threshold for a memory type."""
        if mem_type == MemoryType.PREFERENCE:
            return self.config.preference_archive_days
        if mem_type == MemoryType.CONTEXT:
            return self.config.context_archive_days
        if mem_type == MemoryType.RULE:
            return self.config.pattern_archive_days
        if mem_type == MemoryType.TEMPORAL:
            return self.config.temporal_archive_days
        return 60
