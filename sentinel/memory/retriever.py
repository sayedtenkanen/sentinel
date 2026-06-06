"""Context-aware memory retrieval for Sentinel Memory.

Retrieves relevant memories based on review context (files, language, tags)
and provides context compression for agent injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Memory, MemoryType
from .store import MemoryStore


@dataclass
class RetrievalContext:
    """Context for memory retrieval."""

    file_paths: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    max_memories: int = 10


@dataclass
class RetrievalResult:
    """Result of memory retrieval."""

    memories: list[Memory] = field(default_factory=list)
    context_for_agents: dict[str, Any] = field(default_factory=dict)
    total_available: int = 0
    query_tags: list[str] = field(default_factory=list)


class MemoryRetriever:
    """Retrieves memories from the store based on review context.

    Usage:
        store = MemoryStore("./memory.db")
        retriever = MemoryRetriever(store)
        result = retriever.retrieve(RetrievalContext(languages=["python"]))
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    def retrieve(self, context: RetrievalContext) -> RetrievalResult:
        """Retrieve memories relevant to the review context.

        Queries by tags (language, rule, agent) and returns the most
        relevant memories up to max_memories limit.
        """
        query_tags = self._build_query_tags(context)
        all_memories = self.store.query(tags=query_tags if query_tags else None)

        total_available = len(all_memories)
        memories = all_memories[: context.max_memories]

        context_for_agents = self._build_agent_context(memories, context)

        return RetrievalResult(
            memories=memories,
            context_for_agents=context_for_agents,
            total_available=total_available,
            query_tags=query_tags,
        )

    def retrieve_by_rule(self, rule_id: str) -> list[Memory]:
        """Retrieve memories related to a specific rule."""
        return self.store.query(tags=[rule_id], type=MemoryType.RULE)

    def retrieve_by_language(self, language: str) -> list[Memory]:
        """Retrieve memories relevant to a specific language."""
        return self.store.query(tags=[language])

    def retrieve_by_agent(self, agent_name: str) -> list[Memory]:
        """Retrieve memories relevant to a specific agent."""
        return self.store.query(tags=[agent_name])

    def get_preferences(self) -> list[Memory]:
        """Retrieve all user preferences."""
        return self.store.query(type=MemoryType.PREFERENCE)

    def get_context(self) -> list[Memory]:
        """Retrieve all project context memories."""
        return self.store.query(type=MemoryType.CONTEXT)

    def _build_query_tags(self, context: RetrievalContext) -> list[str]:
        """Build query tags from retrieval context."""
        tags: list[str] = []

        tags.extend(context.languages)
        tags.extend(context.rule_ids)
        tags.extend(context.agents)
        tags.extend(context.tags)

        return list(set(tags))

    def _build_agent_context(
        self, memories: list[Memory], _context: RetrievalContext
    ) -> dict[str, Any]:
        """Build context dict for injection into agents."""
        if not memories:
            return {}

        rules = [m for m in memories if m.type == MemoryType.RULE]
        preferences = [m for m in memories if m.type == MemoryType.PREFERENCE]
        project_context = [m for m in memories if m.type == MemoryType.CONTEXT]

        return {
            "memory_count": len(memories),
            "rules": [m.content for m in rules],
            "preferences": [m.content for m in preferences],
            "context": [m.content for m in project_context],
            "summary": self._summarize_memories(memories),
        }

    def _summarize_memories(self, memories: list[Memory]) -> str:
        """Create a summary of retrieved memories for agent context."""
        if not memories:
            return ""

        lines = ["Relevant memories from past reviews:"]

        for mem in memories[:5]:
            mem_type = mem.type.value
            content_summary = str(mem.content)[:100]
            lines.append(f"- [{mem_type}] {content_summary}")

        if len(memories) > 5:
            lines.append(f"- ...and {len(memories) - 5} more")

        return "\n".join(lines)
