"""Base parser interface for language-agnostic source code analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Abstract base for language parsers.

    Implementations convert source code into structured data that agents
    consume. Every analysis method returns simple dict/list structures
    so agents remain language-agnostic.
    """

    @abstractmethod
    def compute_complexity(self, source: str) -> tuple[int, int]:
        """Return (cyclomatic_complexity, max_nesting_depth)."""

    @abstractmethod
    def find_function_lengths(self, source: str) -> list[dict]:
        """Return list of {name, line, length, complexity, nesting, params}."""

    @abstractmethod
    def find_unused_imports(self, source: str) -> list[dict]:
        """Return list of {name, line}. May be empty if detection not supported."""

    @abstractmethod
    def parse_imports(self, source: str) -> list[str]:
        """Return top-level module names imported."""

    @abstractmethod
    def find_functions_with_docstrings(self, source: str) -> list[dict]:
        """Return list of {name, line, has_docstring, type} (type='function'|'class')."""

    @abstractmethod
    def find_mutable_defaults(self, source: str) -> list[dict]:
        """Return list of {name, line} where mutable defaults found. Empty if N/A."""

    @abstractmethod
    def find_too_many_params(self, source: str, max_params: int) -> list[dict]:
        """Return list of {name, line, params} exceeding threshold."""

    @abstractmethod
    def find_missing_type_hints(self, source: str) -> list[dict]:
        """Return list of {name, line}. Empty if N/A."""

    @abstractmethod
    def find_module_has_docstring(self, source: str) -> bool:
        """True if source has a module-level docstring."""

    @abstractmethod
    def find_undocumented_params(self, source: str) -> list[dict]:
        """Return list of {function, param, line} for undocumented params."""

    @abstractmethod
    def find_inconsistent_returns(self, source: str) -> list[dict]:
        """Return list of {name, line} with mixed bare/valued returns."""

    @abstractmethod
    def find_unnecessary_else(self, source: str) -> list[dict]:
        """Return list of {line} for unnecessary else after return/raise/break."""

    @abstractmethod
    def find_naming_violations(self, source: str) -> list[dict]:
        """Return list of {name, line, kind} (kind='class'|'function')."""

    @abstractmethod
    def find_shadowed_builtins(self, source: str, builtins: set[str] | None = None) -> list[dict]:
        """Return list of {name, line, kind} for names shadowing builtins."""
