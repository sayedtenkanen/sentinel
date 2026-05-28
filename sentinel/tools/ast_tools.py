"""AST-based analysis utilities for complexity and imports."""

from __future__ import annotations

import ast
from typing import Any


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1
        self.max_nesting = 0
        self._current_nesting = 0

    def _branch(self, node: ast.AST) -> None:
        self.complexity += 1
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)
        self.generic_visit(node)
        self._current_nesting -= 1

    def visit_If(self, node: ast.If) -> None:
        self._branch(node)

    def visit_While(self, node: ast.While) -> None:
        self._branch(node)

    def visit_For(self, node: ast.For) -> None:
        self._branch(node)

    def visit_And(self, node: ast.And) -> None:
        self._branch(node)

    def visit_Or(self, node: ast.Or) -> None:
        self._branch(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._branch(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._branch(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._branch(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._branch(node)

    def visit_With(self, node: ast.With) -> None:
        self._branch(node)


def compute_complexity(source: str) -> tuple[int, int]:
    try:
        tree = ast.parse(source)
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        return visitor.complexity, visitor.max_nesting
    except SyntaxError:
        return 0, 0


def find_function_lengths(source: str) -> list[dict[str, Any]]:
    results = []
    try:
        tree = ast.parse(source)
        source.split("\n")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno or 0
                end = node.end_lineno or start
                length = end - start + 1
                results.append(
                    {
                        "name": node.name,
                        "line": start,
                        "length": length,
                    }
                )
    except SyntaxError:
        pass
    return results


def find_unused_imports(source: str) -> list[dict[str, Any]]:
    unused = []
    try:
        tree = ast.parse(source)
        names_in_scope = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names_in_scope.add(node.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if name not in names_in_scope and name != "__future__":
                        unused.append(
                            {
                                "name": alias.name,
                                "line": node.lineno or 0,
                            }
                        )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    if name not in names_in_scope:
                        unused.append(
                            {
                                "name": f"{node.module or ''}.{alias.name}",
                                "line": node.lineno or 0,
                            }
                        )
    except SyntaxError:
        pass
    return unused
