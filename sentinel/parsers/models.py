"""Typed data models for parser output.

Replaces loose dicts with typed dataclasses so agents consume
consistent, well-defined structures regardless of source language.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FunctionLength:
    name: str
    line: int
    length: int
    complexity: int
    nesting: int
    params: int


@dataclass
class UnusedImport:
    name: str
    line: int


@dataclass
class DocstringInfo:
    name: str
    line: int
    has_docstring: bool
    type: str  # "function" | "class"


@dataclass
class MutableDefault:
    name: str
    line: int


@dataclass
class ParamOverflow:
    name: str
    line: int
    params: int


@dataclass
class MissingTypeHint:
    name: str
    line: int


@dataclass
class UndocumentedParam:
    function: str
    param: str
    line: int


@dataclass
class InconsistentReturn:
    name: str
    line: int


@dataclass
class UnnecessaryElse:
    line: int


@dataclass
class NamingViolation:
    name: str
    line: int
    kind: str  # "class" | "function"


@dataclass
class ShadowedBuiltin:
    name: str
    line: int
    kind: str  # "function" | "class"


__all__ = [
    "DocstringInfo",
    "FunctionLength",
    "InconsistentReturn",
    "MissingTypeHint",
    "MutableDefault",
    "NamingViolation",
    "ParamOverflow",
    "ShadowedBuiltin",
    "UndocumentedParam",
    "UnnecessaryElse",
    "UnusedImport",
]
