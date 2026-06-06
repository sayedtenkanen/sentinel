"""Go parser — regex/line-based analysis for .go files.

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

GO_BUILTINS = {
    "append",
    "cap",
    "clear",
    "close",
    "complex",
    "copy",
    "delete",
    "imag",
    "len",
    "make",
    "max",
    "min",
    "new",
    "panic",
    "print",
    "println",
    "real",
    "recover",
    "error",
    "bool",
    "byte",
    "comparable",
    "complex64",
    "complex128",
    "float32",
    "float64",
    "int",
    "int8",
    "int16",
    "int32",
    "int64",
    "rune",
    "string",
    "uint",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "uintptr",
    "any",
    "iota",
    "nil",
    "true",
    "false",
}

_GO_FUNC_RE = re.compile(r"func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\(")
_GO_FUNC_WITH_PARAMS_RE = re.compile(r"func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\(([^)]*)\)")


class GoParser(BaseParser):
    """Parser for Go using regex/line heuristics."""

    def compute_complexity(self, source: str) -> tuple[int, int]:
        complexity = 1
        nest_depth = 0
        max_nest = 0
        for line in source.split("\n"):
            stripped = line.strip()
            open_braces = stripped.count("{") - stripped.count("}")
            if any(
                kw in stripped
                for kw in (
                    "if ",
                    "else if ",
                    "for ",
                    "switch ",
                    "select ",
                    "case ",
                )
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
        for match in _GO_FUNC_RE.finditer(source):
            name = match.group(1)
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
                1 for kw in ("if ", "for ", "switch ", "select ", "case ") if kw in body
            )
            param_count = self._count_params(source, match.start(), bracket_start)
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

    def _count_params(self, source: str, match_start: int, bracket_start: int) -> int:
        """Count parameters by isolating the param list from the signature."""
        sig = source[match_start:bracket_start]
        paren_start = sig.find("(")
        if paren_start == -1:
            return 0
        sig_after_paren = sig[paren_start:]
        param_count = len(re.findall(r",", sig_after_paren))
        if sig_after_paren.startswith("("):
            param_count += 1
        return param_count

    def find_unused_imports(self, source: str) -> list[UnusedImport]:
        results: list[UnusedImport] = []
        imports: list[tuple[str, int]] = []
        imports_end = 0
        group_re = re.compile(r"import\s*\(")
        single_re = re.compile(r'import\s+"([^"]+)"')
        for m in group_re.finditer(source):
            block_start = m.end()
            block_end = source.find(")", block_start)
            if block_end == -1:
                continue
            block = source[block_start:block_end]
            for line_offset, line in enumerate(block.split("\n")):
                stripped = line.strip()
                if not stripped or stripped.startswith("//"):
                    continue
                pkg_match = re.search(r'"([^"]+)"', stripped)
                if pkg_match:
                    pkg = pkg_match.group(1)
                    line_num = source[:block_start].count("\n") + line_offset + 1
                    imports.append((pkg, line_num))
            imports_end = max(imports_end, block_end)
        for m in single_re.finditer(source):
            pkg = m.group(1)
            line_num = source[: m.start()].count("\n") + 1
            imports.append((pkg, line_num))
            imports_end = max(imports_end, m.end())
        body_start = imports_end
        body = source[body_start:]
        for pkg, line_num in imports:
            pkg_name = pkg.rsplit("/", 1)[-1]
            if pkg_name not in body:
                results.append(UnusedImport(name=pkg, line=line_num))
        return results

    def parse_imports(self, source: str) -> list[str]:
        imports: list[str] = []
        group_re = re.compile(r"import\s*\(")
        single_re = re.compile(r'import\s+"([^"]+)"')
        for m in group_re.finditer(source):
            block_start = m.end()
            block_end = source.find(")", block_start)
            if block_end == -1:
                continue
            block = source[block_start:block_end]
            for pkg_match in re.finditer(r'"([^"]+)"', block):
                imports.append(pkg_match.group(1))
        for m in single_re.finditer(source):
            imports.append(m.group(1))
        return sorted(set(imports))

    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]:
        results: list[DocstringInfo] = []
        lines = source.split("\n")
        for i, line in enumerate(lines):
            match = _GO_FUNC_RE.search(line)
            if not match:
                continue
            name = match.group(1)
            has_docstring = False
            for j in range(i - 1, max(i - 5, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("//"):
                    has_docstring = True
                    break
                if prev.startswith("/*"):
                    has_docstring = True
                    break
                if prev and not prev.startswith(")"):
                    break
            results.append(
                DocstringInfo(
                    name=name,
                    line=i + 1,
                    has_docstring=has_docstring,
                    type="function",
                )
            )
        return results

    def find_mutable_defaults(self, source: str) -> list[MutableDefault]:
        return []

    def find_too_many_params(self, source: str, max_params: int) -> list[ParamOverflow]:
        results: list[ParamOverflow] = []
        for match in _GO_FUNC_WITH_PARAMS_RE.finditer(source):
            name = match.group(1)
            params_str = match.group(2).strip()
            if not params_str:
                continue
            param_count = len(re.findall(r",", params_str)) + 1
            if param_count > max_params:
                line = source[: match.start()].count("\n") + 1
                results.append(ParamOverflow(name=name, line=line, params=param_count))
        return results

    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]:
        return []

    def find_module_has_docstring(self, source: str) -> bool:
        stripped = source.lstrip()
        return stripped.startswith("//") or stripped.startswith("/*")

    def find_undocumented_params(self, source: str) -> list[UndocumentedParam]:
        return []

    def find_inconsistent_returns(self, source: str) -> list[InconsistentReturn]:
        return []

    def find_unnecessary_else(self, source: str) -> list[UnnecessaryElse]:
        return []

    def find_naming_violations(self, source: str) -> list[NamingViolation]:
        results: list[NamingViolation] = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            func_match = _GO_FUNC_RE.match(stripped)
            if func_match:
                name = func_match.group(1)
                if name[0].isupper() and not self._is_valid_exported_name(name):
                    results.append(NamingViolation(name=name, line=i, kind="function"))
            type_match = re.match(r"type\s+(\w+)\s+struct", stripped)
            if type_match:
                name = type_match.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]+$", name):
                    results.append(NamingViolation(name=name, line=i, kind="type"))
        return results

    def _is_valid_exported_name(self, name: str) -> bool:
        """Check if an exported name follows Go conventions.

        Go exported names start with an uppercase letter. Special names
        like Test*, Benchmark*, and Example* use prefix-based rules.
        """
        if re.match(r"^[A-Z][a-zA-Z0-9]+$", name):
            return True
        for prefix in ("Test", "Benchmark", "Example"):
            if name.startswith(prefix) and len(name) > len(prefix):
                rest = name[len(prefix) :]
                if rest[0].isupper():
                    return True
        return name in ("Main", "Init")

    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]:
        results: list[ShadowedBuiltin] = []
        builtins_set = builtins or GO_BUILTINS
        for match in re.finditer(r"(?:var\s+(\w+)|(\w+)\s*:=)", source):
            name = match.group(1) or match.group(2)
            if name in builtins_set:
                line = source[: match.start()].count("\n") + 1
                results.append(ShadowedBuiltin(name=name, line=line, kind="variable"))
        return results
