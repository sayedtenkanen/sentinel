"""Tests for Sentinel Memory graph abstraction."""

import os
import tempfile
import unittest

from sentinel.memory.graph import Graph, GraphState, Node, linear_graph


class TestGraphState(unittest.TestCase):
    def test_default_state(self):
        state = GraphState()
        self.assertEqual(state.review_events, [])
        self.assertEqual(state.feedback_events, [])
        self.assertEqual(state.candidates, [])
        self.assertEqual(state.errors, [])

    def test_to_dict(self):
        state = GraphState()
        state.candidates = ["test"]
        d = state.to_dict()
        self.assertEqual(d["candidates"], ["test"])

    def test_from_dict(self):
        d = {"candidates": ["a", "b"], "errors": ["err1"]}
        state = GraphState.from_dict(d)
        self.assertEqual(state.candidates, ["a", "b"])
        self.assertEqual(state.errors, ["err1"])


class TestNode(unittest.TestCase):
    def test_execute(self):
        def add_candidate(state):
            state.candidates.append("new")
            return state

        node = Node(name="add", fn=add_candidate)
        state = GraphState()
        result = node.execute(state)
        self.assertEqual(result.candidates, ["new"])

    def test_condition_true(self):
        node = Node(name="n", fn=lambda s: s, condition=lambda _: True)
        self.assertTrue(node.should_run(GraphState()))

    def test_condition_false(self):
        node = Node(name="n", fn=lambda s: s, condition=lambda _: False)
        self.assertFalse(node.should_run(GraphState()))

    def test_no_condition(self):
        node = Node(name="n", fn=lambda s: s)
        self.assertTrue(node.should_run(GraphState()))


class TestGraph(unittest.TestCase):
    def test_linear_execution(self):
        order = []

        def make_node(name):
            def fn(state):
                order.append(name)
                return state

            return Node(name=name, fn=fn)

        graph = Graph(
            nodes=[make_node("a"), make_node("b"), make_node("c")],
            edges=[("a", "b"), ("b", "c")],
        )

        graph.run(GraphState())
        self.assertEqual(order, ["a", "b", "c"])

    def test_conditional_skip(self):
        order = []

        def make_node(name, condition=None):
            def fn(state):
                order.append(name)
                return state

            return Node(name=name, fn=fn, condition=condition)

        graph = Graph(
            nodes=[
                make_node("a"),
                make_node("b", condition=lambda _: False),
                make_node("c"),
            ],
            edges=[("a", "b"), ("b", "c")],
        )

        graph.run(GraphState())
        self.assertEqual(order, ["a", "c"])

    def test_topological_sort(self):
        # b -> a -> c
        graph = Graph(
            nodes=[
                Node(name="a", fn=lambda s: s),
                Node(name="b", fn=lambda s: s),
                Node(name="c", fn=lambda s: s),
            ],
            edges=[("b", "a"), ("a", "c")],
        )
        order = graph._resolve_execution_order()
        self.assertLess(order.index("b"), order.index("a"))
        self.assertLess(order.index("a"), order.index("c"))

    def test_cycle_detection(self):
        graph = Graph(
            nodes=[Node(name="a", fn=lambda s: s), Node(name="b", fn=lambda s: s)],
            edges=[("a", "b"), ("b", "a")],
        )
        with self.assertRaises(ValueError) as ctx:
            graph._resolve_execution_order()
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_duplicate_node_error(self):
        graph = Graph(nodes=[Node(name="a", fn=lambda s: s)])
        with self.assertRaises(ValueError) as ctx:
            graph.add_node(Node(name="a", fn=lambda s: s))
        self.assertIn("already exists", str(ctx.exception))

    def test_missing_source_error(self):
        graph = Graph(nodes=[Node(name="b", fn=lambda s: s)])
        with self.assertRaises(ValueError) as ctx:
            graph.add_edge(("a", "b"))
        self.assertIn("not found", str(ctx.exception))

    def test_node_error_captures(self):
        def fail(state):
            raise RuntimeError("boom")

        graph = Graph(
            nodes=[Node(name="a", fn=fail), Node(name="b", fn=lambda s: s)],
            edges=[("a", "b")],
        )
        state = graph.run(GraphState())
        self.assertEqual(len(state.errors), 1)
        self.assertIn("boom", state.errors[0])


class TestCheckpoint(unittest.TestCase):
    def test_pickle_checkpoint(self):
        graph = Graph(nodes=[Node(name="a", fn=lambda s: s)])
        state = GraphState()
        state.candidates = ["test"]

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            graph.checkpoint(state, path, format="pickle")
            restored = graph.restore(path, format="pickle")
            self.assertEqual(restored.candidates, ["test"])
        finally:
            os.unlink(path)

    def test_json_checkpoint(self):
        graph = Graph(nodes=[Node(name="a", fn=lambda s: s)])
        state = GraphState()
        state.candidates = ["test"]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            graph.checkpoint(state, path, format="json")
            restored = graph.restore(path, format="json")
            self.assertEqual(restored.candidates, ["test"])
        finally:
            os.unlink(path)


class TestVisualize(unittest.TestCase):
    def test_linear_viz(self):
        graph = linear_graph("a", "b", "c")
        viz = graph.visualize()
        self.assertIn("Graph:", viz)
        self.assertIn("a -> b", viz)
        self.assertIn("b -> c", viz)
        self.assertIn("[END]", viz)

    def test_repr(self):
        graph = linear_graph("a", "b")
        self.assertEqual(repr(graph), "Graph(nodes=2, edges=1)")


class TestLinearGraph(unittest.TestCase):
    def test_creates_linear(self):
        graph = linear_graph("x", "y", "z")
        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(graph.edges), 2)

    def test_execution(self):
        order = []

        def track(name):
            def fn(state):
                order.append(name)
                return state

            return fn

        graph = Graph(
            nodes=[
                Node(name="a", fn=track("a")),
                Node(name="b", fn=track("b")),
            ],
            edges=[("a", "b")],
        )
        graph.run(GraphState())
        self.assertEqual(order, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
