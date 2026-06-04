"""AST-based import dependency graph builder for architecture analysis.

Builds a directed graph of module dependencies, detects cycles,
computes fan-in/fan-out metrics, and identifies god modules.
"""

from __future__ import annotations

import ast
from collections import defaultdict


def parse_imports(source: str) -> list[str]:
    """Extract module-level import names from source code.

    source: Python source code.
    """
    imports: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            base = node.module.split(".")[0]
            if base not in imports:
                imports.append(base)
    return sorted(set(imports))


class ImportGraph:
    """Directed graph of module dependencies built from source files."""

    def __init__(self) -> None:
        self._nodes: set[str] = set()
        self._edges: dict[str, set[str]] = defaultdict(set)

    def add_module(self, module: str, imports: list[str]) -> None:
        self._nodes.add(module)
        for imp in imports:
            if imp != module:
                self._edges[module].add(imp)
                self._nodes.add(imp)

    def add_file(self, file_path: str, source: str) -> None:
        module = file_path.replace(".py", "").replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        imports = parse_imports(source)
        self.add_module(module, imports)

    @property
    def nodes(self) -> set[str]:
        return self._nodes

    @property
    def edges(self) -> dict[str, set[str]]:
        return dict(self._edges)

    def fan_in(self, module: str) -> int:
        count = 0
        for deps in self._edges.values():
            if module in deps:
                count += 1
        return count

    def fan_out(self, module: str) -> int:
        return len(self._edges.get(module, set()))

    def dependencies(self, module: str) -> set[str]:
        return self._edges.get(module, set())

    def dependents(self, module: str) -> list[str]:
        return [m for m in self._nodes if module in self._edges.get(m, set())]

    def find_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycle = [*path[cycle_start:], node]
                cycles.append(cycle)
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in self._edges.get(node, set()):
                if neighbor in self._nodes:
                    dfs(neighbor)
            path.pop()

        for node in sorted(self._nodes):
            if node not in visited:
                dfs(node)
        return cycles

    def find_god_modules(self, threshold: int = 10) -> list[tuple[str, int, int]]:
        results: list[tuple[str, int, int]] = []
        for node in sorted(self._nodes):
            fi = self.fan_in(node)
            fo = self.fan_out(node)
            if fo >= threshold:
                results.append((node, fi, fo))
        return results

    def coupling_summary(self) -> dict:
        if not self._nodes:
            return {"modules": 0, "avg_fan_in": 0.0, "avg_fan_out": 0.0, "cycles": 0}
        total_fi = sum(self.fan_in(n) for n in self._nodes)
        total_fo = sum(self.fan_out(n) for n in self._nodes)
        n = len(self._nodes)
        return {
            "modules": n,
            "total_edges": sum(len(deps) for deps in self._edges.values()),
            "avg_fan_in": round(total_fi / n, 2),
            "avg_fan_out": round(total_fo / n, 2),
            "cycles": len(self.find_cycles()),
            "god_modules": len(self.find_god_modules()),
        }
