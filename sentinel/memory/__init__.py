"""Sentinel Memory — Dreaming-style memory system.

Implements a LangGraph-inspired pipeline for extracting, validating,
resolving, and synthesizing memories from code review sessions.

Modules:
    graph: DAG executor with state threading and checkpointing
    metrics: Run, memory, and user quality metrics
    store: SQLite-backed persistent memory storage
    models: Memory, MemoryCandidate, ReviewEvent, FeedbackEvent
    retriever: Context-aware memory retrieval
    extractor: Pattern mining from feedback (extraction node)
    validator: Verify patterns against codebase (validation node)
    conflict: Resolve contradictory memories (conflict node)
    synthesizer: Combine related memories (synthesis node)
    temporal: Aging, decay, expiration
    eval: Evaluation metrics
"""

from sentinel.memory.graph import Edge, Graph, GraphState, Node, linear_graph
from sentinel.memory.metrics import (
    MemoryMetrics,
    MetricsStore,
    RunMetrics,
    UserMetrics,
)

__all__ = [
    "Edge",
    "Graph",
    "GraphState",
    "MemoryMetrics",
    "MetricsStore",
    "Node",
    "RunMetrics",
    "UserMetrics",
    "linear_graph",
]
