"""Tool Registry — discoverable direct tools for the hybrid execution agent.

Wraps existing sentinel/tools/ functions as typed, documented tools that
the execution agent can discover and call. Provides help text generation
for agent prompts (template §5: direct tools).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Param:
    name: str
    type_str: str
    default: object = None
    required: bool = True
    description: str = ""


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., object]
    parameters: list[Param] = field(default_factory=list)
    returns: str = ""


def _type_name(t: object) -> str:
    if t is inspect.Parameter.empty:
        return "Any"
    name = getattr(t, "__name__", None)
    if isinstance(name, str):
        return name
    return str(t)


def _build_params(func: Callable[..., object]) -> list[Param]:
    sig = inspect.signature(func)
    params: list[Param] = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        p = Param(
            name=name,
            type_str=_type_name(param.annotation),
            default=param.default if param.default is not inspect.Parameter.empty else None,
            required=param.default is inspect.Parameter.empty,
        )
        params.append(p)
    return params


def _build_returns(func: Callable[..., object]) -> str:
    sig = inspect.signature(func)
    hint = sig.return_annotation
    if hint is inspect.Parameter.empty or hint is inspect.Signature.empty:
        return "Any"
    if hasattr(hint, "__name__"):
        return hint.__name__
    return str(hint)


class ToolRegistry:
    """Registry of typed, documented tools for the execution agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self, fn: Callable[..., object], name: str | None = None, description: str | None = None
    ) -> Tool:
        tool_name = name or getattr(fn, "__name__", "") or type(fn).__name__
        tool_desc = description or (fn.__doc__ or "").strip() or f"Calls {tool_name}"
        tool = Tool(
            name=tool_name,
            description=tool_desc.split("\n")[0],
            fn=fn,
            parameters=_build_params(fn),
            returns=_build_returns(fn),
        )
        self._tools[tool_name] = tool
        return tool

    def register_many(self, **fns: Callable[..., object]) -> None:
        for name, fn in fns.items():
            self.register(fn, name=name)

    def get(self, tool_name: str) -> Tool | None:
        return self._tools.get(tool_name)

    def list_tools(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def call(self, tool_name: str, **kwargs: object) -> object:
        tool = self.get(tool_name)
        if tool is None:
            msg = f"Unknown tool: {tool_name}"
            raise KeyError(msg)
        return tool.fn(**kwargs)

    def get_help(self) -> str:
        parts = ["## Available Direct Tools\n"]
        for tool in self.list_tools():
            parts.append(f"### {tool.name}")
            parts.append(f"{tool.description}")
            params_desc = ", ".join(
                f"{p.name}: {p.type_str}{' (optional)' if not p.required else ''}"
                for p in tool.parameters
            )
            if params_desc:
                parts.append(f"  Params: {params_desc}")
            parts.append(f"  Returns: {tool.returns}")
            parts.append("")
        return "\n".join(parts)


_default_registry: ToolRegistry | None = None


def default_registry() -> ToolRegistry:
    global _default_registry
    if _default_registry is not None:
        return _default_registry

    from . import ast_tools, git_tools, secrets_scanner

    reg = ToolRegistry()
    reg.register(ast_tools.compute_complexity, name="compute_complexity")
    reg.register(ast_tools.find_function_lengths, name="find_function_lengths")
    reg.register(ast_tools.find_unused_imports, name="find_unused_imports")
    reg.register(
        secrets_scanner.scan_file,
        name="scan_secrets",
        description="Scan text content for hardcoded secrets, API keys, and credentials",
    )
    reg.register(git_tools.parse_diff, name="parse_diff")
    reg.register(git_tools.detect_language, name="detect_language")

    from .import_graph import ImportGraph

    ig = ImportGraph()
    reg.register(
        ig.add_file,
        name="import_graph_add_file",
        description="Add a file's imports to the dependency graph",
    )
    reg.register(
        ig.find_cycles,
        name="import_graph_find_cycles",
        description="Find circular dependencies in the import graph",
    )
    reg.register(
        ig.find_god_modules,
        name="import_graph_find_god_modules",
        description="Find modules that import too many other modules",
    )
    reg.register(
        ig.coupling_summary,
        name="import_graph_summary",
        description="Get a summary of module coupling metrics",
    )
    _default_registry = reg
    return reg
