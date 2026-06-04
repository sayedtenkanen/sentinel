"""Unit tests for the import graph builder."""

import unittest

from sentinel.tools.import_graph import ImportGraph, parse_imports


class TestParseImports(unittest.TestCase):
    def test_simple_import(self):
        imports = parse_imports("import os\nimport sys\n")
        self.assertIn("os", imports)
        self.assertIn("sys", imports)

    def test_from_import(self):
        imports = parse_imports("from collections import Counter, defaultdict")
        self.assertIn("collections", imports)

    def test_stdlib_vs_third_party(self):
        imports = parse_imports("import json\nimport requests\nimport flask")
        self.assertIn("json", imports)
        self.assertIn("requests", imports)
        self.assertIn("flask", imports)

    def test_relative_import(self):
        imports = parse_imports("from . import utils")
        self.assertEqual(imports, [])

    def test_no_imports(self):
        imports = parse_imports("x = 1\nprint(x)\n")
        self.assertEqual(imports, [])

    def test_syntax_error(self):
        imports = parse_imports("x = 1 + ")
        self.assertEqual(imports, [])

    def test_empty(self):
        imports = parse_imports("")
        self.assertEqual(imports, [])

    def test_import_as(self):
        imports = parse_imports("import numpy as np")
        self.assertIn("numpy", imports)

    def test_submodule_import(self):
        imports = parse_imports("import os.path")
        self.assertIn("os", imports)

    def test_unique_imports(self):
        imports = parse_imports("import os\nimport os\nimport sys\n")
        self.assertEqual(len(imports), 2)


class TestImportGraph(unittest.TestCase):
    def setUp(self):
        self.graph = ImportGraph()

    def test_empty_graph(self):
        self.assertEqual(len(self.graph.nodes), 0)
        self.assertEqual(len(self.graph.edges), 0)

    def test_add_module(self):
        self.graph.add_module("app.main", ["os", "sys", "app.utils"])
        self.assertIn("app.main", self.graph.nodes)
        self.assertIn("os", self.graph.nodes)

    def test_fan_in(self):
        self.graph.add_module("app.a", ["x", "y"])
        self.graph.add_module("app.b", ["x", "z"])
        self.graph.add_module("app.c", ["x"])
        self.assertEqual(self.graph.fan_in("x"), 3)

    def test_fan_out(self):
        self.graph.add_module("app.main", ["os", "sys", "json"])
        self.assertEqual(self.graph.fan_out("app.main"), 3)

    def test_fan_out_zero(self):
        self.graph.add_module("isolated", [])
        self.assertEqual(self.graph.fan_out("isolated"), 0)

    def test_fan_in_zero(self):
        self.graph.add_module("orphan", [])
        self.assertEqual(self.graph.fan_in("orphan"), 0)

    def test_dependencies(self):
        deps = ["os", "sys", "json"]
        self.graph.add_module("app.main", deps)
        self.assertEqual(self.graph.dependencies("app.main"), set(deps))

    def test_dependents(self):
        self.graph.add_module("a", ["shared"])
        self.graph.add_module("b", ["shared"])
        deps = self.graph.dependents("shared")
        self.assertIn("a", deps)
        self.assertIn("b", deps)

    def test_no_cycles(self):
        self.graph.add_module("a", ["b"])
        self.graph.add_module("b", ["c"])
        self.graph.add_module("c", [])
        self.assertEqual(len(self.graph.find_cycles()), 0)

    def test_direct_cycle(self):
        self.graph.add_module("a", ["b"])
        self.graph.add_module("b", ["a"])
        cycles = self.graph.find_cycles()
        self.assertGreater(len(cycles), 0)

    def test_self_import_ignored(self):
        self.graph.add_module("a", ["a"])
        self.assertEqual(len(self.graph.find_cycles()), 0)

    def test_god_modules(self):
        deps = [f"lib{i}" for i in range(15)]
        self.graph.add_module("god", deps)
        gods = self.graph.find_god_modules(threshold=10)
        self.assertEqual(len(gods), 1)
        self.assertEqual(gods[0][0], "god")

    def test_god_modules_below_threshold(self):
        self.graph.add_module("normal", ["a", "b", "c"])
        gods = self.graph.find_god_modules(threshold=10)
        self.assertEqual(len(gods), 0)

    def test_add_file(self):
        source = "import os\nimport sys\nfrom collections import Counter\n"
        self.graph.add_file("app/main.py", source)
        self.assertIn("app.main", self.graph.nodes)
        self.assertIn("os", self.graph.nodes)

    def test_add_file_init(self):
        source = "import flask\n"
        self.graph.add_file("app/__init__.py", source)
        self.assertIn("app", self.graph.nodes)

    def test_coupling_summary(self):
        self.graph.add_module("a", ["b", "c"])
        self.graph.add_module("b", ["c"])
        self.graph.add_module("c", [])
        summary = self.graph.coupling_summary()
        self.assertEqual(summary["modules"], 3)
        self.assertEqual(summary["total_edges"], 3)
        self.assertGreater(summary["avg_fan_in"], 0)

    def test_coupling_summary_empty(self):
        summary = ImportGraph().coupling_summary()
        self.assertEqual(summary["modules"], 0)


class TestImportGraphIntegration(unittest.TestCase):
    def test_chain_detected(self):
        graph = ImportGraph()
        graph.add_module("a", ["b"])
        graph.add_module("b", ["c"])
        graph.add_module("c", [])
        self.assertEqual(len(graph.find_cycles()), 0)

    def test_complex_cycle(self):
        graph = ImportGraph()
        graph.add_module("a", ["b"])
        graph.add_module("b", ["c", "d"])
        graph.add_module("c", ["e"])
        graph.add_module("d", ["a"])
        graph.add_module("e", [])
        cycles = graph.find_cycles()
        self.assertGreater(len(cycles), 0)
        self.assertIn("a", cycles[0])

    def test_disconnected_graph(self):
        graph = ImportGraph()
        graph.add_module("a", ["b"])
        graph.add_module("c", ["d"])
        graph.add_module("x", [])
        self.assertEqual(len(graph.find_cycles()), 0)
        self.assertEqual(len(graph.nodes), 5)


if __name__ == "__main__":
    unittest.main()
