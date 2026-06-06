"""Sentinel Memory — Dreaming-style memory system.

Implements a LangGraph-inspired pipeline for extracting, validating,
resolving, and synthesizing memories from code review sessions.

Modules:
    graph: DAG executor with state threading and checkpointing
    metrics: Run, memory, and user quality metrics
    models: Memory, MemoryCandidate, ReviewEvent, FeedbackEvent
    store: SQLite-backed persistent memory storage
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
from sentinel.memory.models import (
    FeedbackEvent,
    Memory,
    MemoryCandidate,
    MemoryType,
    ReviewEvent,
)
from sentinel.memory.store import MemoryStore

__all__ = [
    "Edge",
    "FeedbackEvent",
    "Graph",
    "GraphState",
    "Memory",
    "MemoryCandidate",
    "MemoryMetrics",
    "MemoryStore",
    "MemoryType",
    "MetricsStore",
    "Node",
    "ReviewEvent",
    "RunMetrics",
    "UserMetrics",
    "linear_graph",
]
