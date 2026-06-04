"""Python parser — moves all ast.* calls behind the BaseParser interface."""

from __future__ import annotations

import ast
import re

from .base import BaseParser
from .models import (
    DocstringInfo,
    FunctionLength,
    InconsistentReturn,
    MissingTypeHint,
    MutableDefault,
    NamingViolation,
    ParamOverflow,
    ShadowedBuiltin,
    UndocumentedParam,
    UnnecessaryElse,
    UnusedImport,
)


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


PY_BUILTINS = {
    "list",
    "dict",
    "str",
    "int",
    "float",
    "bool",
    "set",
    "tuple",
    "type",
    "object",
    "input",
    "print",
    "len",
    "range",
    "map",
    "filter",
    "zip",
    "open",
    "file",
    "id",
    "eval",
    "exec",
    "max",
    "min",
    "sum",
    "any",
    "all",
    "abs",
    "round",
    "sorted",
    "reversed",
    "enumerate",
    "iter",
    "next",
    "property",
    "staticmethod",
    "classmethod",
    "super",
    "Exception",
    "BaseException",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "ImportError",
}


class PythonParser(BaseParser):
    """Parser for Python using the built-in ast module."""

    def compute_complexity(self, source: str) -> tuple[int, int]:
        try:
            tree = ast.parse(source)
            visitor = ComplexityVisitor()
            visitor.visit(tree)
            return visitor.complexity, visitor.max_nesting
        except SyntaxError:
            return 0, 0

    def find_function_lengths(self, source: str) -> list[FunctionLength]:
        results: list[FunctionLength] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.lineno or 0
                    end = node.end_lineno or start
                    length = end - start + 1
                    visitor = ComplexityVisitor()
                    visitor.visit(node)
                    params = len(node.args.args) + len(node.args.posonlyargs)
                    if node.args.vararg:
                        params += 1
                    if node.args.kwonlyargs:
                        params += len(node.args.kwonlyargs)
                    if node.args.kwarg:
                        params += 1
                    results.append(
                        FunctionLength(
                            name=node.name,
                            line=start,
                            length=length,
                            complexity=visitor.complexity,
                            nesting=visitor.max_nesting,
                            params=params,
                        )
                    )
        except SyntaxError:
            pass
        return results

    def find_unused_imports(self, source: str) -> list[UnusedImport]:
        unused: list[UnusedImport] = []
        try:
            tree = ast.parse(source)
            names_in_scope: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names_in_scope.add(node.id)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        if name not in names_in_scope and name != "__future__":
                            unused.append(
                                UnusedImport(
                                    name=alias.name,
                                    line=node.lineno or 0,
                                )
                            )
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        name = alias.asname or alias.name
                        if name not in names_in_scope:
                            unused.append(
                                UnusedImport(
                                    name=f"{node.module or ''}.{alias.name}",
                                    line=node.lineno or 0,
                                )
                            )
        except SyntaxError:
            pass
        return unused

    def parse_imports(self, source: str) -> list[str]:
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

    def _has_docstring(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module
    ) -> bool:
        return (
            bool(node.body)
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]:
        results: list[DocstringInfo] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    results.append(
                        DocstringInfo(
                            name=node.name,
                            line=node.lineno or 0,
                            has_docstring=bool(node.body and self._has_docstring(node)),
                            type="function",
                        )
                    )
                elif isinstance(node, ast.ClassDef):
                    results.append(
                        DocstringInfo(
                            name=node.name,
                            line=node.lineno or 0,
                            has_docstring=bool(node.body and self._has_docstring(node)),
                            type="class",
                        )
                    )
        except SyntaxError:
            pass
        return results

    def find_mutable_defaults(self, source: str) -> list[MutableDefault]:
        results: list[MutableDefault] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            results.append(
                                MutableDefault(
                                    name=node.name,
                                    line=default.lineno or 0,
                                )
                            )
        except SyntaxError:
            pass
        return results

    def find_too_many_params(self, source: str, max_params: int) -> list[ParamOverflow]:
        results: list[ParamOverflow] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    param_count = len(node.args.args) + len(node.args.kwonlyargs)
                    if node.args.vararg:
                        param_count += 1
                    if node.args.kwarg:
                        param_count += 1
                    if param_count > max_params:
                        results.append(
                            ParamOverflow(
                                name=node.name,
                                line=node.lineno or 0,
                                params=param_count,
                            )
                        )
        except SyntaxError:
            pass
        return results

    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]:
        results: list[MissingTypeHint] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    returns_hint = node.returns is not None
                    params_hint = all(
                        arg.annotation is not None or arg.arg == "self" for arg in node.args.args
                    )
                    if not returns_hint or not params_hint:
                        results.append(
                            MissingTypeHint(
                                name=node.name,
                                line=node.lineno or 0,
                            )
                        )
        except SyntaxError:
            pass
        return results

    def find_module_has_docstring(self, source: str) -> bool:
        try:
            tree = ast.parse(source)
            if not tree.body:
                return False
            return (
                isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            )
        except SyntaxError:
            return False

    def find_undocumented_params(self, source: str) -> list[UndocumentedParam]:
        results: list[UndocumentedParam] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.body:
                    continue
                first_stmt = node.body[0]
                has_docstring = (
                    isinstance(first_stmt, ast.Expr)
                    and isinstance(first_stmt.value, ast.Constant)
                    and isinstance(first_stmt.value.value, str)
                )
                if not has_docstring:
                    continue
                doc = first_stmt.value.value
                actual_params = {
                    arg.arg for arg in node.args.args if arg.arg != "self" and arg.arg != "cls"
                }
                doc_params = set(re.findall(r"^\s*([\w_]+)\s*:", doc, re.MULTILINE))
                missing = actual_params - doc_params
                if missing and node.name != "__init__":
                    for param in sorted(missing):
                        results.append(
                            UndocumentedParam(
                                function=node.name,
                                param=param,
                                line=node.lineno or 0,
                            )
                        )
        except SyntaxError:
            pass
        return results

    def find_inconsistent_returns(self, source: str) -> list[InconsistentReturn]:
        results: list[InconsistentReturn] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    has_explicit_return = False
                    has_bare_return = False
                    for child in ast.walk(node):
                        if isinstance(child, ast.Return):
                            if child.value is not None:
                                has_explicit_return = True
                            else:
                                has_bare_return = True
                    if has_explicit_return and has_bare_return:
                        results.append(
                            InconsistentReturn(
                                name=node.name,
                                line=node.lineno or 0,
                            )
                        )
        except SyntaxError:
            pass
        return results

    def find_unnecessary_else(self, source: str) -> list[UnnecessaryElse]:
        results: list[UnnecessaryElse] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.If):
                    continue
                if not node.orelse:
                    continue
                for stmt in node.body:
                    if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                        for else_stmt in node.orelse:
                            if isinstance(else_stmt, ast.If):
                                continue
                        results.append(
                            UnnecessaryElse(
                                line=node.orelse[0].lineno or 0,
                            )
                        )
                        break
        except SyntaxError:
            pass
        return results

    def find_naming_violations(self, source: str) -> list[NamingViolation]:
        results: list[NamingViolation] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    name = node.name
                    if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                        results.append(
                            NamingViolation(
                                name=name,
                                line=node.lineno or 0,
                                kind="class",
                            )
                        )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                    if name[0].isupper() and name != "__init__":
                        results.append(
                            NamingViolation(
                                name=name,
                                line=node.lineno or 0,
                                kind="function",
                            )
                        )
        except SyntaxError:
            pass
        return results

    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]:
        results: list[ShadowedBuiltin] = []
        builtins_set = builtins or PY_BUILTINS
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in builtins_set:
                        results.append(
                            ShadowedBuiltin(
                                name=node.name,
                                line=node.lineno or 0,
                                kind="function",
                            )
                        )
                elif isinstance(node, ast.ClassDef) and node.name in builtins_set:
                    results.append(
                        ShadowedBuiltin(
                            name=node.name,
                            line=node.lineno or 0,
                            kind="class",
                        )
                    )
        except SyntaxError:
            pass
        return results
