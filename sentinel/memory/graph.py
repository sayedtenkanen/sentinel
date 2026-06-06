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
import pickle
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to dict (for checkpointing)."""
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphState:
        """Deserialize state from dict."""
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
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


class Graph:
    """Lightweight DAG executor with checkpointing.

    Features:
        - Linear execution (A → B → C)
        - Conditional routing (if/else edges)
        - Node skipping (condition guards)
        - Checkpoint/restore (pickle or JSON)

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
        if isinstance(edge, tuple):
            edge_obj = Edge(source=edge[0], target=edge[1], condition=condition)  # ty: ignore[invalid-argument-type]
        elif condition is not None:
            edge.condition = condition
            edge_obj = edge
        else:
            edge_obj = edge

        if edge_obj.source not in self.nodes:
            raise ValueError(f"Source node '{edge_obj.source}' not found")
        if edge_obj.target not in self.nodes:
            raise ValueError(f"Target node '{edge_obj.target}' not found")

        self.edges.append(edge_obj)

    def _resolve_execution_order(self) -> list[str]:
        """Topological sort of nodes for linear execution."""
        if self._execution_order:
            return self._execution_order

        # Build adjacency list
        in_degree: dict[str, int] = {name: 0 for name in self.nodes}
        adjacency: dict[str, list[str]] = {name: [] for name in self.nodes}

        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        # Kahn's algorithm
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order: list[str] = []

        while queue:
            current = queue.pop(0)
            order.append(current)
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

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

        current_state = state

        for i in range(start_idx, end_idx):
            node_name = order[i]
            node = self.nodes[node_name]

            # Check node condition
            if not node.should_run(current_state):
                continue

            # Execute node
            try:
                current_state = node.execute(current_state)
            except Exception as e:
                current_state.errors.append(f"Node '{node_name}' failed: {e}")
                break

            # Check edge conditions for early termination
            should_stop = False
            for edge in self.edges:
                if edge.source == node_name and not edge.should_traverse(current_state):
                    should_stop = True
                    break
            if should_stop:
                break

        return current_state

    def checkpoint(self, state: GraphState, path: str, format: str = "pickle") -> None:
        """Save state to checkpoint file."""
        if format == "pickle":
            with open(path, "wb") as f:
                pickle.dump(state, f)
        elif format == "json":
            with open(path, "w") as f:
                json.dump(state.to_dict(), f, indent=2, default=str)
        else:
            raise ValueError(f"Unknown format: {format}")

    def restore(self, path: str, format: str = "pickle") -> GraphState:
        """Restore state from checkpoint file."""
        if format == "pickle":
            with open(path, "rb") as f:
                return pickle.load(f)
        elif format == "json":
            with open(path) as f:
                data = json.load(f)
            return GraphState.from_dict(data)
        else:
            raise ValueError(f"Unknown format: {format}")

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
