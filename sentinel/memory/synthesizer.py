"""Synthesis node for Sentinel Memory pipeline.

Combines related memories, merges similar patterns, and produces
final memories ready for storage.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Memory, MemoryType


@dataclass
class SynthesisConfig:
    """Configuration for memory synthesis."""

    merge_same_rule: bool = True
    merge_same_preference: bool = True
    min_confidence_for_merge: float = 0.7


class MemorySynthesizer:
    """Combines related memories into synthesized memories.

    Usage:
        synthesizer = MemorySynthesizer()
        synthesized = synthesizer.synthesize(memories)
    """

    def __init__(self, config: SynthesisConfig | None = None):
        self.config = config or SynthesisConfig()

    def synthesize(self, memories: list[Memory]) -> list[Memory]:
        """Synthesize memories by merging related ones."""
        if not memories:
            return []

        by_type: dict[MemoryType, list[Memory]] = {}
        for mem in memories:
            if mem.type not in by_type:
                by_type[mem.type] = []
            by_type[mem.type].append(mem)

        synthesized: list[Memory] = []

        for mem_type, type_memories in by_type.items():
            if mem_type == MemoryType.RULE and self.config.merge_same_rule:
                synthesized.extend(self._merge_rules(type_memories))
            elif mem_type == MemoryType.PREFERENCE and self.config.merge_same_preference:
                synthesized.extend(self._merge_preferences(type_memories))
            else:
                synthesized.extend(type_memories)

        return synthesized

    def _merge_rules(self, memories: list[Memory]) -> list[Memory]:
        """Merge memories for the same rule."""
        by_rule: dict[str, list[Memory]] = {}
        for mem in memories:
            rule_id = mem.content.get("rule_id", "unknown")
            if rule_id not in by_rule:
                by_rule[rule_id] = []
            by_rule[rule_id].append(mem)

        merged: list[Memory] = []
        for _rule_id, rule_memories in by_rule.items():
            if len(rule_memories) == 1:
                merged.append(rule_memories[0])
            else:
                merged.append(self._merge_memory_group(rule_memories))

        return merged

    def _merge_preferences(self, memories: list[Memory]) -> list[Memory]:
        """Merge memories for the same user preference."""
        by_user: dict[str, list[Memory]] = {}
        for mem in memories:
            user = mem.content.get("user", "anonymous")
            if user not in by_user:
                by_user[user] = []
            by_user[user].append(mem)

        merged: list[Memory] = []
        for _user, user_memories in by_user.items():
            if len(user_memories) == 1:
                merged.append(user_memories[0])
            else:
                merged.append(self._merge_memory_group(user_memories))

        return merged

    def _merge_memory_group(self, memories: list[Memory]) -> Memory:
        """Merge a group of related memories into one."""
        if not memories:
            raise ValueError("Cannot merge empty memory list")

        best = max(memories, key=lambda m: m.confidence)

        all_tags: list[str] = []
        all_evidence: list[str] = []
        for mem in memories:
            all_tags.extend(mem.tags)
            all_evidence.extend(mem.content.get("evidence", []))

        merged_content = dict(best.content)
        merged_content["evidence"] = list(set(all_evidence))
        merged_content["source_count"] = len(memories)
        merged_content["merged_from"] = [m.id for m in memories]

        avg_confidence = sum(m.confidence for m in memories) / len(memories)

        return Memory(
            type=best.type,
            content=merged_content,
            confidence=avg_confidence,
            source="synthesis",
            tags=list(set(all_tags)),
        )

    def compress_for_context(self, memories: list[Memory], max_tokens: int = 500) -> str:
        """Compress memories into a context string for agent injection."""
        if not memories:
            return ""

        lines: list[str] = []
        current_tokens = 0

        for mem in memories:
            summary = self._memory_to_summary(mem)
            token_estimate = len(summary.split())

            if current_tokens + token_estimate > max_tokens:
                remaining = len(memories) - len(lines)
                if remaining > 0:
                    lines.append(f"\n...and {remaining} more memories")
                break

            lines.append(summary)
            current_tokens += token_estimate

        return "\n".join(lines)

    def _memory_to_summary(self, memory: Memory) -> str:
        """Convert a memory to a concise summary string."""
        mem_type = memory.type.value
        content = memory.content

        if memory.type == MemoryType.RULE:
            rule_id = content.get("rule_id", "unknown")
            pattern = content.get("feedback_pattern", "unknown")
            return f"[{mem_type}] Rule {rule_id}: {pattern} (conf: {memory.confidence:.2f})"

        if memory.type == MemoryType.PREFERENCE:
            user = content.get("user", "anonymous")
            pref = content.get("preferred_feedback", "unknown")
            return f"[{mem_type}] {user} prefers: {pref} (conf: {memory.confidence:.2f})"

        if memory.type == MemoryType.CONTEXT:
            ctx_type = content.get("type", "unknown")
            return f"[{mem_type}] {ctx_type} (conf: {memory.confidence:.2f})"

        return f"[{mem_type}] {str(content)[:80]} (conf: {memory.confidence:.2f})"
