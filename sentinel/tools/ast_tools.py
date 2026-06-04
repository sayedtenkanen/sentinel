"""AST-based analysis utilities — delegates to PythonParser for backward compat."""

from __future__ import annotations

from ..parsers.models import FunctionLength, UnusedImport
from ..parsers.python import PythonParser

_PARSER = PythonParser()


def compute_complexity(source: str) -> tuple[int, int]:
    return _PARSER.compute_complexity(source)


def find_function_lengths(source: str) -> list[FunctionLength]:
    return _PARSER.find_function_lengths(source)


def find_unused_imports(source: str) -> list[UnusedImport]:
    return _PARSER.find_unused_imports(source)
