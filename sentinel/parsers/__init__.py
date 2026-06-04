"""Parser abstraction layer — language-agnostic source code analysis.

Usage:
    from sentinel.parsers import ParserRegistry

    registry = ParserRegistry()
    parser = registry.get("python")   # PythonParser()
    complexity, nesting = parser.compute_complexity(source)
"""

from __future__ import annotations

from .base import BaseParser
from .null import NullParser
from .python import PythonParser


class ParserRegistry:
    """Maps language names to parser instances."""

    def __init__(self) -> None:
        self._parsers: dict[str, BaseParser] = {
            "python": PythonParser(),
        }

    def register(self, language: str, parser: BaseParser) -> None:
        self._parsers[language] = parser

    def get(self, language: str) -> BaseParser | None:
        return self._parsers.get(language)

    def get_or_default(self, language: str) -> BaseParser:
        return self._parsers.get(language) or NullParser()

    def languages(self) -> list[str]:
        return list(self._parsers.keys())


_DEFAULT_REGISTRY: ParserRegistry | None = None


def default_registry() -> ParserRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ParserRegistry()
    return _DEFAULT_REGISTRY


__all__ = ["BaseParser", "NullParser", "ParserRegistry", "PythonParser", "default_registry"]
