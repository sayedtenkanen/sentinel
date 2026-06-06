"""Rust parser — regex/line-based analysis for .rs files.

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

RUST_BUILTINS = {
    "Self",
    "self",
    "super",
    "crate",
    "true",
    "false",
    "Some",
    "None",
    "Ok",
    "Err",
    "String",
    "Vec",
    "Box",
    "Rc",
    "Arc",
    "HashMap",
    "HashSet",
    "Option",
    "Result",
    "bool",
    "char",
    "f32",
    "f64",
    "i8",
    "i16",
    "i32",
    "i64",
    "i128",
    "u8",
    "u16",
    "u32",
    "u64",
    "u128",
    "isize",
    "str",
    "println",
    "eprintln",
    "print",
    "eprint",
    "format",
    "vec",
    "assert",
    "assert_eq",
    "assert_ne",
    "panic",
    "todo",
    "unimplemented",
    "unreachable",
    "dbg",
}

_RUST_FUNC_RE = re.compile(
    r"(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+\"[^\"]*\"\s+)?fn\s+(\w+)"
)
_RUST_STRING_RE = re.compile(r'"([^"\\]|\\.)*"')


def _strip_line_comments(line: str) -> str:
    """Remove inline // comments from a line, preserving strings."""
    result = []
    i = 0
    in_string = False
    while i < len(line):
        if line[i] == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
            result.append(line[i])
        elif not in_string and line[i : i + 2] == "//":
            break
        else:
            result.append(line[i])
        i += 1
    return "".join(result)


def _count_params_in_sig(sig: str) -> int:
    """Count parameters between the first ( and its matching )."""
    paren_start = sig.find("(")
    if paren_start == -1:
        return 0
    depth = 1
    i = paren_start + 1
    while i < len(sig) and depth > 0:
        if sig[i] == "(":
            depth += 1
        elif sig[i] == ")":
            depth -= 1
        i += 1
    param_str = sig[paren_start + 1 : i - 1].strip()
    if not param_str:
        return 0
    return len(re.findall(r",", param_str)) + 1


class RustParser(BaseParser):
    """Parser for Rust using regex/line heuristics."""

    def compute_complexity(self, source: str) -> tuple[int, int]:
        complexity = 1
        nest_depth = 0
        max_nest = 0
        for line in source.split("\n"):
            stripped = line.strip()
            if (
                not stripped
                or stripped.startswith("//")
                or stripped.startswith("/*")
                or stripped.startswith("*")
                or stripped.startswith("*/")
            ):
                continue
            code_part = _strip_line_comments(stripped)
            if not code_part:
                continue
            code_no_strings = _RUST_STRING_RE.sub('""', code_part)
            open_braces = code_no_strings.count("{") - code_no_strings.count("}")
            if any(
                kw in code_no_strings
                for kw in (
                    "if ",
                    "else if ",
                    "for ",
                    "while ",
                    "loop ",
                    "match ",
                )
            ):
                complexity += 1
            if "&&" in code_no_strings:
                complexity += code_no_strings.count("&&")
            if "||" in code_no_strings:
                complexity += code_no_strings.count("||")
            if open_braces > 0:
                nest_depth += open_braces
                max_nest = max(max_nest, nest_depth)
            elif open_braces < 0:
                nest_depth = max(0, nest_depth + open_braces)
        return complexity, max_nest

    def find_function_lengths(self, source: str) -> list[FunctionLength]:
        results: list[FunctionLength] = []
        for match in _RUST_FUNC_RE.finditer(source):
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
                1 for kw in ("if ", "for ", "while ", "loop ", "match ") if kw in body
            )
            sig = source[match.start() : bracket_start]
            param_count = _count_params_in_sig(sig)
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
        results: list[UnusedImport] = []
        imports: list[tuple[str, int]] = []
        imports_end = 0
        use_re = re.compile(r"use\s+([\w:{{}},\s*]+);")
        for m in use_re.finditer(source):
            line_num = source[: m.start()].count("\n") + 1
            import_str = m.group(1).strip()
            if "*" in import_str and "::" in import_str:
                imports_end = max(imports_end, m.end())
                continue
            if "{" in import_str:
                brace_start = import_str.find("{")
                brace_end = import_str.find("}")
                if brace_start != -1 and brace_end != -1:
                    group_content = import_str[brace_start + 1 : brace_end]
                    items = [item.strip() for item in group_content.split(",")]
                    for item in items:
                        if item.strip() == "*":
                            continue
                        alias_match = re.match(r"(\w+(?:::\w+)*)\s+as\s+(\w+)", item)
                        name = alias_match.group(2) if alias_match else item.split("::")[-1].strip()
                        if name and name not in ("self", "super", "crate"):
                            imports.append((name, line_num))
            else:
                alias_match = re.match(r"([\w:]+)\s+as\s+(\w+)", import_str)
                if alias_match:
                    name = alias_match.group(2)
                else:
                    parts = import_str.split("::")
                    name = parts[-1]
                if name not in ("self", "super", "crate"):
                    imports.append((name, line_num))
            imports_end = max(imports_end, m.end())
        body = source[imports_end:]
        for name, line_num in imports:
            pattern = rf"\b{re.escape(name)}\b"
            if not re.search(pattern, body):
                results.append(UnusedImport(name=name, line=line_num))
        return results

    def parse_imports(self, source: str) -> list[str]:
        imports: list[str] = []
        use_re = re.compile(r"use\s+([\w:{{}},\s*]+);")
        for m in use_re.finditer(source):
            import_str = m.group(1).strip()
            if "*" in import_str and "::" in import_str:
                imports.append("*")
                continue
            if "{" in import_str:
                brace_start = import_str.find("{")
                brace_end = import_str.find("}")
                if brace_start != -1 and brace_end != -1:
                    group_content = import_str[brace_start + 1 : brace_end]
                    items = [item.strip() for item in group_content.split(",")]
                    for item in items:
                        if item.strip() == "*":
                            imports.append("*")
                        else:
                            alias_match = re.match(r"(\w+(?:::\w+)*)\s+as\s+(\w+)", item)
                            if alias_match:
                                imports.append(alias_match.group(2))
                            else:
                                imports.append(item)
            else:
                alias_match = re.match(r"([\w:]+)\s+as\s+(\w+)", import_str)
                if alias_match:
                    imports.append(alias_match.group(2))
                else:
                    imports.append(import_str)
        return sorted(set(imports))

    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]:
        results: list[DocstringInfo] = []
        lines = source.split("\n")
        for i, line in enumerate(lines):
            match = _RUST_FUNC_RE.search(line)
            if not match:
                continue
            name = match.group(1)
            has_docstring = False
            for j in range(i - 1, max(i - 10, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("///"):
                    has_docstring = True
                    break
                if prev.startswith("#[") or prev.startswith("pub") or prev.startswith("fn"):
                    break
                if prev and not prev.startswith("//") and not prev.startswith("*"):
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
        func_with_params = re.compile(
            r"(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)\s*\(([^)]*)\)"
        )
        for match in func_with_params.finditer(source):
            name = match.group(1)
            params_str = match.group(2).strip()
            if not params_str:
                continue
            params = [p.strip() for p in params_str.split(",")]
            real_params = [p for p in params if p not in ("&self", "self", "&mut self")]
            if not real_params:
                continue
            param_count = len(real_params)
            if param_count > max_params:
                line = source[: match.start()].count("\n") + 1
                results.append(ParamOverflow(name=name, line=line, params=param_count))
        return results

    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]:
        return []

    def find_module_has_docstring(self, source: str) -> bool:
        stripped = source.lstrip()
        return stripped.startswith("//!") or stripped.startswith("/*!")

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
            func_match = _RUST_FUNC_RE.match(stripped)
            if func_match:
                name = func_match.group(1)
                if not re.match(r"^[a-z][a-z0-9_]*$", name) and name not in (
                    "main",
                    "new",
                    "build",
                    "run",
                    "test",
                ):
                    results.append(NamingViolation(name=name, line=i, kind="function"))
            struct_match = re.match(r"(?:pub\s+)?struct\s+(\w+)", stripped)
            if struct_match:
                name = struct_match.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                    results.append(NamingViolation(name=name, line=i, kind="struct"))
            enum_match = re.match(r"(?:pub\s+)?enum\s+(\w+)", stripped)
            if enum_match:
                name = enum_match.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                    results.append(NamingViolation(name=name, line=i, kind="enum"))
            const_match = re.match(r"(?:pub\s+)?(?:const|static)\s+(\w+)\s*:", stripped)
            if const_match:
                name = const_match.group(1)
                if not re.match(r"^[A-Z][A-Z0-9_]*$", name) and name.isupper():
                    results.append(NamingViolation(name=name, line=i, kind="constant"))
        return results

    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]:
        results: list[ShadowedBuiltin] = []
        builtins_set = builtins or RUST_BUILTINS
        for match in re.finditer(r"let\s+(?:mut\s+)?(\w+)", source):
            name = match.group(1)
            if name in builtins_set:
                line = source[: match.start()].count("\n") + 1
                results.append(ShadowedBuiltin(name=name, line=line, kind="variable"))
        return results
