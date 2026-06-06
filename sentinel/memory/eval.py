"""Memory evaluation metrics for Sentinel Memory.

Provides precision, recall, and other metrics for measuring
memory system effectiveness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Memory, MemoryType
from .store import MemoryStore


@dataclass
class EvaluationResult:
    """Result of memory evaluation."""

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    total_queries: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    memories_evaluated: int = 0
    details: dict = field(default_factory=dict)


class MemoryEvaluator:
    """Evaluates memory system effectiveness.

    Usage:
        evaluator = MemoryEvaluator(store)
        result = evaluator.evaluate(test_queries)
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    def evaluate(
        self,
        test_queries: list[dict] | None = None,
    ) -> EvaluationResult:
        """Run evaluation on the memory store."""
        all_memories = self.store.list_all()
        result = EvaluationResult(memories_evaluated=len(all_memories))

        if not test_queries:
            return self._evaluate_empty(all_memories, result)

        return self._evaluate_queries(test_queries, all_memories, result)

    def _evaluate_empty(self, memories: list[Memory], result: EvaluationResult) -> EvaluationResult:
        """Evaluate with no test queries — just check store health."""
        by_type: dict[MemoryType, int] = {}
        for mem in memories:
            by_type[mem.type] = by_type.get(mem.type, 0) + 1

        result.details = {
            "store_health": "ok",
            "by_type": {k.value: v for k, v in by_type.items()},
            "avg_confidence": self._avg_confidence(memories),
        }
        return result

    def _evaluate_queries(
        self,
        test_queries: list[dict],
        _all_memories: list[Memory],
        result: EvaluationResult,
    ) -> EvaluationResult:
        """Evaluate against labeled test queries."""
        tp = 0
        fp = 0
        fn = 0

        for query in test_queries:
            expected = query.get("expected_memories", [])
            tags = query.get("tags", [])
            mem_type = query.get("type")

            retrieved = self._query_store(tags, mem_type)
            retrieved_ids = {m.id for m in retrieved}
            expected_ids = set(expected)

            tp += len(retrieved_ids & expected_ids)
            fp += len(retrieved_ids - expected_ids)
            fn += len(expected_ids - retrieved_ids)

        result.true_positives = tp
        result.false_positives = fp
        result.false_negatives = fn
        result.total_queries = len(test_queries)

        result.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        result.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        result.f1 = (
            2 * result.precision * result.recall / (result.precision + result.recall)
            if (result.precision + result.recall) > 0
            else 0.0
        )

        return result

    def _query_store(self, tags: list[str], mem_type: MemoryType | None) -> list[Memory]:
        """Query the store with given tags and type."""
        if mem_type:
            return self.store.query(tags=tags if tags else None, type=mem_type)
        return self.store.query(tags=tags if tags else None)

    def _avg_confidence(self, memories: list[Memory]) -> float:
        """Calculate average confidence across memories."""
        if not memories:
            return 0.0
        return sum(m.confidence for m in memories) / len(memories)

    def precision_at_k(self, tags: list[str], expected_ids: list[str], k: int = 5) -> float:
        """Calculate precision@k for a query."""
        retrieved = self.store.query(tags=tags)[:k]
        retrieved_ids = {m.id for m in retrieved}
        expected_set = set(expected_ids)
        return len(retrieved_ids & expected_set) / k if k > 0 else 0.0

    def coverage(self) -> dict[str, Any]:
        """Calculate memory coverage metrics."""
        all_memories = self.store.list_all()
        if not all_memories:
            return {"total": 0, "by_type": {}, "coverage_ratio": 0.0}

        by_type: dict[str, int] = {}
        for mem in all_memories:
            key = mem.type.value
            by_type[key] = by_type.get(key, 0) + 1

        return {
            "total": len(all_memories),
            "by_type": by_type,
            "avg_confidence": self._avg_confidence(all_memories),
        }
