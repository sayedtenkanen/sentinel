"""JavaScript parser — regex/line-based analysis for JS/JSX/TS code.

Uses lightweight heuristics (not a full AST) for practical coverage.
Ideal for code review where 80% accuracy on common patterns suffices.
"""

# ruff: noqa: ARG002

from __future__ import annotations

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

JS_BUILTINS = {
    "undefined",
    "NaN",
    "Infinity",
    "eval",
    "parseInt",
    "parseFloat",
    "isNaN",
    "isFinite",
    "decodeURI",
    "encodeURI",
    "console",
    "window",
    "document",
    "Math",
    "JSON",
    "Array",
    "Object",
    "String",
    "Number",
    "Boolean",
    "Map",
    "Set",
    "Promise",
    "Symbol",
    "Error",
    "Date",
    "RegExp",
    "Function",
    "class",
    "this",
    "arguments",
    "require",
    "module",
    "exports",
    "__dirname",
    "__filename",
    "global",
}


class JavaScriptParser(BaseParser):
    """Parser for JavaScript and TypeScript using regex/line heuristics."""

    def compute_complexity(self, source: str) -> tuple[int, int]:
        complexity = 1
        nest_depth = 0
        max_nest = 0
        for line in source.split("\n"):
            stripped = line.strip()
            open_braces = stripped.count("{") - stripped.count("}")
            if any(
                kw in stripped for kw in ("if ", "else if ", "for ", "while ", "catch ", "case ")
            ):
                complexity += 1
            if "&&" in stripped:
                complexity += stripped.count("&&")
            if "||" in stripped:
                complexity += stripped.count("||")
            if open_braces > 0:
                nest_depth += open_braces
                max_nest = max(max_nest, nest_depth)
            elif open_braces < 0:
                nest_depth = max(0, nest_depth + open_braces)
        return complexity, max_nest

    def find_function_lengths(self, source: str) -> list[FunctionLength]:
        results: list[FunctionLength] = []
        func_re = re.compile(
            r"(?:function\s+\*?\s*(\w+)|(\w+)\s*=\s*(?:async\s+)?(?:function|\(.*\)\s*=>)|"
            r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{)"
        )
        for match in func_re.finditer(source):
            name = match.group(1) or match.group(2) or match.group(3) or "<anonymous>"
            start_line = source[: match.start()].count("\n") + 1
            bracket_start = source.find("{", match.start())
            if bracket_start == -1:
                continue
            depth = 1
            end = bracket_start + 1
            while end < len(source) and depth > 0:
                if source[end] == "{":
                    depth += 1
                elif source[end] == "}":
                    depth -= 1
                end += 1
            end_line = source[:end].count("\n") + 1
            length = end_line - start_line + 1
            body = source[bracket_start:end]
            body_complexity = sum(
                1 for kw in ("if ", "for ", "while ", "catch ", "case ") if kw in body
            )
            param_count = len(
                re.findall(r"(\w+)\s*(?:,|\s*=>|\s*\))", source[match.start() : bracket_start])
            )
            results.append(
                FunctionLength(
                    name=name,
                    line=start_line,
                    length=length,
                    complexity=body_complexity + 1,
                    nesting=0,
                    params=param_count,
                )
            )
        return results

    def find_unused_imports(self, source: str) -> list[UnusedImport]:
        return []

    def parse_imports(self, source: str) -> list[str]:
        imports: list[str] = []
        for m in re.finditer(
            r'(?:import\s+(?:\w+\s*,?\s*)?\{(?:[^}]*)\}\s*from\s+["\']([^"\']+)["\']|require\(["\']([^"\']+)["\']\))',
            source,
        ):
            imports.append(m.group(1) or m.group(2))
        return sorted(set(imports))

    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]:
        results: list[DocstringInfo] = []
        for match in re.finditer(
            r"(/\*\*[\s\S]*?\*/)?\s*(?:function\s+(\w+)|(?:async\s+)?(\w+)\s*\(|class\s+(\w+))",
            source,
        ):
            jsdoc = match.group(1)
            name = match.group(2) or match.group(3) or match.group(4) or ""
            if not name:
                continue
            line = source[: match.start()].count("\n") + 1
            results.append(
                DocstringInfo(
                    name=name,
                    line=line,
                    has_docstring=bool(jsdoc and "/**" in jsdoc),
                    type="function" if match.group(4) is None else "class",
                )
            )
        return results

    def find_mutable_defaults(self, source: str) -> list[MutableDefault]:
        return []

    def find_too_many_params(self, source: str, max_params: int) -> list[ParamOverflow]:
        results: list[ParamOverflow] = []
        for match in re.finditer(
            r"(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))\s*\(([^)]*)\)",
            source,
        ):
            name = match.group(1) or match.group(2)
            params_str = match.group(3).strip()
            param_count = len(re.findall(r"\w+", params_str)) if params_str else 0
            if param_count > max_params:
                line = source[: match.start()].count("\n") + 1
                results.append(ParamOverflow(name=name, line=line, params=param_count))
        return results

    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]:
        return []

    def find_module_has_docstring(self, source: str) -> bool:
        stripped = source.lstrip()
        return stripped.startswith("/**") or stripped.startswith("//")

    def find_undocumented_params(self, source: str) -> list[UndocumentedParam]:
        return []

    def find_inconsistent_returns(self, source: str) -> list[InconsistentReturn]:
        results: list[InconsistentReturn] = []
        func_re = re.compile(
            r"(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?(?:function|=>)|(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{)"
        )
        for func_match in func_re.finditer(source):
            name = func_match.group(1) or func_match.group(2) or func_match.group(3) or ""
            if not name:
                continue
            bracket_start = source.find("{", func_match.start())
            if bracket_start == -1:
                continue
            depth = 1
            end = bracket_start + 1
            while end < len(source) and depth > 0:
                if source[end] == "{":
                    depth += 1
                elif source[end] == "}":
                    depth -= 1
                end += 1
            body = source[bracket_start:end]
            has_valued = bool(re.search(r"return\s+\S", body))
            has_bare = bool(re.search(r"return\s*[;}]", body))
            if has_valued and has_bare:
                line = source[: func_match.start()].count("\n") + 1
                results.append(InconsistentReturn(name=name, line=line))
        return results

    def find_unnecessary_else(self, source: str) -> list[UnnecessaryElse]:
        return []

    def find_naming_violations(self, source: str) -> list[NamingViolation]:
        results: list[NamingViolation] = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            class_match = re.match(r"class\s+(\w+)", stripped)
            if class_match:
                name = class_match.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                    results.append(NamingViolation(name=name, line=i, kind="class"))
            func_match = re.match(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", stripped)
            if func_match:
                name = func_match.group(1)
                if name[0].isupper() and not name.isupper():
                    results.append(NamingViolation(name=name, line=i, kind="function"))
        return results

    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]:
        results: list[ShadowedBuiltin] = []
        builtins_set = builtins or JS_BUILTINS
        for match in re.finditer(r"(?:function|const|let|var)\s+(\w+)", source):
            name = match.group(1)
            if name in builtins_set:
                line = source[: match.start()].count("\n") + 1
                results.append(ShadowedBuiltin(name=name, line=line, kind="function"))
        return results
