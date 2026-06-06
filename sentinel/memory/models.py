"""Data models for Sentinel Memory.

Defines the core types for memories, candidates, events, and feedback
that flow through the memory pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MemoryType(str, Enum):
    """Types of memories that can be stored."""

    RULE = "rule"
    PREFERENCE = "preference"
    CONTEXT = "context"
    TEMPORAL = "temporal"


@dataclass
class Memory:
    """A verified memory stored in the memory base.

    Attributes:
        id: Unique identifier.
        type: Category of memory.
        content: Structured content (rule, preference, or context).
        confidence: Confidence score (0.0 - 1.0).
        created_at: When the memory was created.
        last_used_at: When the memory was last retrieved.
        expires_at: Optional expiration time.
        source: Origin of the memory (e.g., "feedback_pattern", "manual").
        tags: Tags for filtering and retrieval.
    """

    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    type: MemoryType = MemoryType.CONTEXT
    content: dict = field(default_factory=dict)
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None
    source: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class MemoryCandidate:
    """A candidate memory extracted from review sessions.

    Candidates go through validation before becoming memories.
    """

    id: str = field(default_factory=lambda: f"candidate_{uuid.uuid4().hex[:12]}")
    type: MemoryType = MemoryType.CONTEXT
    content: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ReviewEvent:
    """An event from a code review session."""

    file_path: str = ""
    finding_id: str = ""
    rule_id: str = ""
    severity: str = ""
    agent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    code_content: str = ""
    language: str = ""
    file_context: str = ""  # tests/, src/, docs/


@dataclass
class FeedbackEvent:
    """User feedback on a finding."""

    finding_id: str = ""
    rating: str = ""  # correct, incorrect, unsure
    comment: str = ""
    user: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
