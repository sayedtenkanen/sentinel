"""LangGraph-style graph abstraction for Sentinel Memory.

Implements lightweight DAG execution with checkpointing, state threading,
and conditional routing. Zero external dependencies.

Usage:
    from sentinel.memory.graph import Graph, Node, GraphState

    # Define processing functions
    def extract(state: GraphState) -> GraphState:
        state.candidates = [...]
        return state

    def validate(state: GraphState) -> GraphState:
        state.validated = [c for c in state.candidates if c.confidence > 0.6]
        return state

    # Build graph
    graph = Graph(
        nodes=[
            Node(name="extract", fn=extract),
            Node(name="validate", fn=validate),
        ],
        edges=[("extract", "validate")]
    )

    # Run
    state = graph.run(state)
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class GraphState:
    """Typed state flowing through the graph.

    Attributes are added dynamically by nodes — this is the base schema.
    Extend by subclassing or adding fields as needed.
    """

    review_events: list[Any] = field(default_factory=list)
    feedback_events: list[Any] = field(default_factory=list)
    candidates: list[Any] = field(default_factory=list)
    validated: list[Any] = field(default_factory=list)
    conflicts: list[tuple[Any, Any]] = field(default_factory=list)
    resolved: list[Any] = field(default_factory=list)
    synthesized: list[Any] = field(default_factory=list)
    memories_to_store: list[Any] = field(default_factory=list)
    context_for_agents: dict[str, Any] = field(default_factory=dict)
    metrics: Any = None
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to dict (for checkpointing).

        Preserves both declared fields and dynamically-added extras.
        """
        from dataclasses import asdict

        result = asdict(self)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphState:
        """Deserialize state from dict.

        Restores declared fields and stores unknown keys in extras.
        """
        state = cls()
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        for key, value in data.items():
            if key in known_fields:
                setattr(state, key, value)
            elif key != "__dataclass_fields__":
                state.extras[key] = value
        return state


@dataclass
class Node:
    """Processing step — pure function: GraphState → GraphState.

    Attributes:
        name: Unique node identifier.
        fn: Processing function.
        condition: Optional guard — skip node if this returns False.
    """

    name: str
    fn: Callable[[GraphState], GraphState]
    condition: Callable[[GraphState], bool] | None = None

    def should_run(self, state: GraphState) -> bool:
        """Check if this node should execute."""
        if self.condition is None:
            return True
        return self.condition(state)

    def execute(self, state: GraphState) -> GraphState:
        """Run the node's function."""
        return self.fn(state)


@dataclass
class Edge:
    """Directed edge between two nodes."""

    source: str
    target: str
    condition: Callable[[GraphState], bool] | None = None

    def should_traverse(self, state: GraphState) -> bool:
        if self.condition is None:
            return True
        return self.condition(state)


def _build_adjacency(
    edges: list[Edge], node_names: set[str]
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Build adjacency list and in-degree map from edges."""
    adjacency: dict[str, list[str]] = {name: [] for name in node_names}
    in_degree: dict[str, int] = {name: 0 for name in node_names}

    for edge in edges:
        adjacency[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    return adjacency, in_degree


def _topological_sort(adjacency: dict[str, list[str]], in_degree: dict[str, int]) -> list[str]:
    """Kahn's algorithm for topological ordering."""
    queue = deque(name for name, degree in in_degree.items() if degree == 0)
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in adjacency[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


def _validate_range(order: list[str], start: str | None, end: str | None) -> tuple[int, int]:
    """Validate start/end nodes and return (start_idx, end_idx).

    Raises ValueError if start comes after end in execution order.
    """
    start_idx = 0
    end_idx = len(order)

    if start:
        if start not in order:
            raise ValueError(f"Start node '{start}' not found")
        start_idx = order.index(start)

    if end:
        if end not in order:
            raise ValueError(f"End node '{end}' not found")
        end_idx = order.index(end) + 1

    if start is not None and end is not None and start_idx >= end_idx:
        raise ValueError(
            f"Invalid execution range: start node '{start}' comes after end node '{end}'"
        )

    return start_idx, end_idx


def _execute_node(node: Node, state: GraphState) -> tuple[GraphState, bool]:
    """Execute a node, returning (new_state, should_continue)."""
    if not node.should_run(state):
        return state, True

    try:
        new_state = node.execute(state)
    except Exception as e:
        state.errors.append(f"Node '{node.name}' failed: {e}")
        return state, False

    return new_state, True


def _check_edge_termination(edges: list[Edge], source: str, state: GraphState) -> bool:
    """Check if any outgoing edge from source should terminate execution."""
    return any(edge.source == source and not edge.should_traverse(state) for edge in edges)


class Graph:
    """Lightweight DAG executor with checkpointing.

    Features:
        - Linear execution (A → B → C)
        - Conditional routing (if/else edges)
        - Node skipping (condition guards)
        - Checkpoint/restore (JSON only)

    Usage:
        graph = Graph(nodes=[a, b, c], edges=[("a", "b"), ("b", "c")])
        state = graph.run(initial_state)
    """

    def __init__(
        self,
        nodes: list[Node] | None = None,
        edges: list[tuple[str, str] | Edge] | None = None,
    ):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._execution_order: list[str] = []

        if nodes:
            for node in nodes:
                self.add_node(node)

        if edges:
            for edge in edges:
                self.add_edge(edge)

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        if node.name in self.nodes:
            raise ValueError(f"Node '{node.name}' already exists")
        self.nodes[node.name] = node

    def add_edge(
        self,
        edge: tuple[str, str] | Edge,
        condition: Callable[[GraphState], bool] | None = None,
    ) -> None:
        """Add an edge between two nodes."""
        edge_obj = self._make_edge(edge, condition)

        if edge_obj.source not in self.nodes:
            raise ValueError(f"Source node '{edge_obj.source}' not found")
        if edge_obj.target not in self.nodes:
            raise ValueError(f"Target node '{edge_obj.target}' not found")

        self.edges.append(edge_obj)

    def _make_edge(
        self,
        edge: tuple[str, str] | Edge,
        condition: Callable[[GraphState], bool] | None,
    ) -> Edge:
        """Convert tuple or Edge with optional condition override."""
        if isinstance(edge, tuple):
            return Edge(source=edge[0], target=edge[1], condition=condition)  # ty: ignore[invalid-argument-type]
        if condition is not None:
            edge.condition = condition
        return edge

    def _resolve_execution_order(self) -> list[str]:
        """Topological sort of nodes for linear execution."""
        if self._execution_order:
            return self._execution_order

        adjacency, in_degree = _build_adjacency(self.edges, set(self.nodes.keys()))
        order = _topological_sort(adjacency, in_degree)

        if len(order) != len(self.nodes):
            raise ValueError("Graph contains a cycle")

        self._execution_order = order
        return order

    def run(
        self,
        state: GraphState,
        start: str | None = None,
        end: str | None = None,
    ) -> GraphState:
        """Execute the graph.

        Args:
            state: Initial graph state.
            start: Optional start node (default: first in topological order).
            end: Optional end node (stop after this node).

        Returns:
            Final graph state after all nodes execute.
        """
        order = self._resolve_execution_order()
        start_idx, end_idx = _validate_range(order, start, end)
        current_state = state

        for i in range(start_idx, end_idx):
            node_name = order[i]
            node = self.nodes[node_name]

            current_state, should_continue = _execute_node(node, current_state)
            if not should_continue:
                break

            if _check_edge_termination(self.edges, node_name, current_state):
                break

        return current_state

    def checkpoint(self, state: GraphState, path: str) -> None:
        """Save state to JSON checkpoint file."""
        with open(path, "w") as f:
            json.dump(state.to_dict(), f, indent=2, default=str)

    def restore(self, path: str) -> GraphState:
        """Restore state from JSON checkpoint file."""
        with open(path) as f:
            data = json.load(f)
        return GraphState.from_dict(data)

    def visualize(self) -> str:
        """Return ASCII representation of the graph."""
        order = self._resolve_execution_order()
        lines = []

        for i, name in enumerate(order):
            node = self.nodes[name]
            has_condition = node.condition is not None
            marker = " [conditional]" if has_condition else ""

            if i < len(order) - 1:
                next_name = order[i + 1]
                lines.append(f"  {name}{marker} -> {next_name}")
            else:
                lines.append(f"  {name}{marker} [END]")

        # Add conditional edges
        for edge in self.edges:
            if edge.condition is not None:
                lines.append(f"  {edge.source} --?--> {edge.target}")

        return "Graph:\n" + "\n".join(lines)

    def __repr__(self) -> str:
        return f"Graph(nodes={len(self.nodes)}, edges={len(self.edges)})"


def linear_graph(*node_names: str) -> Graph:
    """Create a simple linear graph: A -> B -> C -> ..."""
    nodes = [Node(name=name, fn=lambda state: state) for name in node_names]
    graph = Graph(nodes=nodes)
    for i in range(len(node_names) - 1):
        graph.add_edge((node_names[i], node_names[i + 1]))
    return graph
