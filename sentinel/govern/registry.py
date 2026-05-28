"""Agent Registry — discoverability for agents and configs (ADLC Govern phase).

Provides a registry of available agents, their capabilities, config schemas,
and defaults. Enables dynamic agent discovery and profile sharing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentInfo:
    name: str
    description: str
    version: str = "1.0.0"
    config_schema: dict[str, dict] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "config_schema": self.config_schema,
            "capabilities": self.capabilities,
            "tags": self.tags,
        }


@dataclass
class AgentRegistry:
    agents: dict[str, AgentInfo] = field(default_factory=dict)

    def register(self, info: AgentInfo) -> None:
        self.agents[info.name] = info

    def unregister(self, name: str) -> bool:
        if name in self.agents:
            del self.agents[name]
            return True
        return False

    def get(self, name: str) -> AgentInfo | None:
        return self.agents.get(name)

    def list_agents(self) -> list[AgentInfo]:
        return sorted(self.agents.values(), key=lambda a: a.name)

    def find_by_tag(self, tag: str) -> list[AgentInfo]:
        return [a for a in self.agents.values() if tag in a.tags]

    def find_by_capability(self, capability: str) -> list[AgentInfo]:
        return [a for a in self.agents.values() if capability in a.capabilities]

    def to_dict(self) -> dict:
        return {"agents": [a.to_dict() for a in self.list_agents()]}

    @classmethod
    def default(cls) -> AgentRegistry:
        registry = cls()
        registry.register(
            AgentInfo(
                name="static-analysis",
                description=(
                    "Cyclomatic complexity, line length, nesting depth, unused imports,"
                    " trailing whitespace, blank lines, param count, shadowed builtins"
                ),
                version="1.0.0",
                config_schema={
                    "complexity_threshold": {
                        "type": "int",
                        "default": 25,
                        "description": "Maximum cyclomatic complexity",
                    },
                    "max_function_length": {
                        "type": "int",
                        "default": 50,
                        "description": "Maximum function lines",
                    },
                    "max_line_length": {
                        "type": "int",
                        "default": 100,
                        "description": "Maximum line length",
                    },
                    "max_nesting_depth": {
                        "type": "int",
                        "default": 6,
                        "description": "Maximum nesting depth",
                    },
                    "max_params": {
                        "type": "int",
                        "default": 8,
                        "description": "Maximum function parameters",
                    },
                },
                capabilities=["static-analysis", "complexity", "linting"],
                tags=["core", "code-quality"],
            )
        )
        registry.register(
            AgentInfo(
                name="security",
                description=(
                    "32 security patterns: eval, exec, pickle, SQLi, shell injection,"
                    " hardcoded creds, secrets, XSS, SSTI, and more"
                ),
                version="1.0.0",
                config_schema={},
                capabilities=["security", "vulnerability-scanning"],
                tags=["core", "security"],
            )
        )
        registry.register(
            AgentInfo(
                name="style",
                description=(
                    "Import ordering, naming conventions (CapWords, snake_case),"
                    " docstrings, magic numbers, is vs == checks"
                ),
                version="1.0.0",
                config_schema={},
                capabilities=["style", "conventions"],
                tags=["core", "code-quality"],
            )
        )
        registry.register(
            AgentInfo(
                name="best-practices",
                description=(
                    "Bare excepts, lambda assigns, mutable defaults, globals, type hints,"
                    " context manager enforcement, type comparisons"
                ),
                version="1.0.0",
                config_schema={},
                capabilities=["best-practices", "correctness"],
                tags=["core", "code-quality"],
            )
        )
        registry.register(
            AgentInfo(
                name="documentation",
                description="Module/function/class docstrings, inline comments ratio, documentation coverage",
                version="1.0.0",
                config_schema={},
                capabilities=["documentation", "coverage"],
                tags=["core", "docs"],
            )
        )
        registry.register(
            AgentInfo(
                name="summary",
                description="Compiles final verdict, severity breakdown, and cost summary",
                version="1.0.0",
                config_schema={},
                capabilities=["reporting", "summary"],
                tags=["core", "reporting"],
            )
        )
        registry.register(
            AgentInfo(
                name="llm-review",
                description="Optional LLM-powered review with RAG context retrieval",
                version="1.0.0",
                config_schema={
                    "api_key": {"type": "string", "default": "", "description": "OpenAI API key"},
                    "model": {
                        "type": "string",
                        "default": "gpt-4o-mini",
                        "description": "Model name",
                    },
                    "rag_top_k": {
                        "type": "int",
                        "default": 3,
                        "description": "RAG results to retrieve",
                    },
                },
                capabilities=["llm", "rag", "ai-review"],
                tags=["optional", "llm"],
            )
        )
        return registry
