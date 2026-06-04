"""Null parser — returns empty results for unsupported languages.

All analysis methods return safe defaults (empty lists, zero scores)
so agents gracefully skip files in languages they cannot parse.
"""

# ruff: noqa: ARG002

from __future__ import annotations

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


class NullParser(BaseParser):
    """Parser for unsupported languages — every method returns empty/zero data."""

    def compute_complexity(self, source: str) -> tuple[int, int]:
        return 1, 0

    def find_function_lengths(self, source: str) -> list[FunctionLength]:
        return []

    def find_unused_imports(self, source: str) -> list[UnusedImport]:
        return []

    def parse_imports(self, source: str) -> list[str]:
        return []

    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]:
        return []

    def find_mutable_defaults(self, source: str) -> list[MutableDefault]:
        return []

    def find_too_many_params(self, source: str, max_params: int) -> list[ParamOverflow]:
        return []

    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]:
        return []

    def find_module_has_docstring(self, source: str) -> bool:
        return False

    def find_undocumented_params(self, source: str) -> list[UndocumentedParam]:
        return []

    def find_inconsistent_returns(self, source: str) -> list[InconsistentReturn]:
        return []

    def find_unnecessary_else(self, source: str) -> list[UnnecessaryElse]:
        return []

    def find_naming_violations(self, source: str) -> list[NamingViolation]:
        return []

    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]:
        return []
