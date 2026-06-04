"""Base parser interface for language-agnostic source code analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod

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


class BaseParser(ABC):
    """Abstract base for language parsers.

    Implementations convert source code into typed model objects
    so agents remain language-agnostic.
    """

    @abstractmethod
    def compute_complexity(self, source: str) -> tuple[int, int]:
        """Return (cyclomatic_complexity, max_nesting_depth)."""

    @abstractmethod
    def find_function_lengths(self, source: str) -> list[FunctionLength]: ...

    @abstractmethod
    def find_unused_imports(self, source: str) -> list[UnusedImport]: ...

    @abstractmethod
    def parse_imports(self, source: str) -> list[str]:
        """Return top-level module names imported."""

    @abstractmethod
    def find_functions_with_docstrings(self, source: str) -> list[DocstringInfo]: ...

    @abstractmethod
    def find_mutable_defaults(self, source: str) -> list[MutableDefault]: ...

    @abstractmethod
    def find_too_many_params(self, source: str, max_params: int) -> list[ParamOverflow]: ...

    @abstractmethod
    def find_missing_type_hints(self, source: str) -> list[MissingTypeHint]: ...

    @abstractmethod
    def find_module_has_docstring(self, source: str) -> bool:
        """True if source has a module-level docstring."""

    @abstractmethod
    def find_undocumented_params(self, source: str) -> list[UndocumentedParam]: ...

    @abstractmethod
    def find_inconsistent_returns(self, source: str) -> list[InconsistentReturn]: ...

    @abstractmethod
    def find_unnecessary_else(self, source: str) -> list[UnnecessaryElse]: ...

    @abstractmethod
    def find_naming_violations(self, source: str) -> list[NamingViolation]: ...

    @abstractmethod
    def find_shadowed_builtins(
        self, source: str, builtins: set[str] | None = None
    ) -> list[ShadowedBuiltin]: ...
