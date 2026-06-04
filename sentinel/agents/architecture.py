"""Architecture smell agent — import graph analysis, cycles, coupling, god modules.

Deterministic agent that analyzes module dependencies for architectural
issues. Complements the execution agent by providing basic architecture
checks without requiring an LLM.
"""

from __future__ import annotations

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity
from ..tools.import_graph import ImportGraph


class ArchitectureAgent(BaseAgent):
    name = "architecture"
    description = "Import graph analysis: cycles, coupling, god modules, layering"

    def __init__(self, enabled: bool = True, god_module_threshold: int = 10) -> None:
        super().__init__(name=self.name, enabled=enabled)
        self._graph = ImportGraph()
        self._god_module_threshold = god_module_threshold

    def analyze(self, file: FileContext) -> list[Finding]:
        if not file.content.strip():
            return []
        self._graph.add_file(file.path, file.content)
        return self._check_file(file)

    def _check_file(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        module = file.path.replace(".py", "").replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]

        cycles = self._graph.find_cycles()
        for cycle in cycles:
            if module in cycle:
                cycle_str = " → ".join(cycle)
                findings.append(
                    self.finding(
                        severity=Severity.HIGH,
                        message=f"Circular import detected: {cycle_str}",
                        suggestion=(
                            "Extract shared dependencies into a common module or "
                            "restructure to remove the cycle"
                        ),
                        file=file.path,
                        line=1,
                        rule_id="ARC001",
                        category="architecture",
                    )
                )

        fo = self._graph.fan_out(module)
        if fo >= self._god_module_threshold:
            fi = self._graph.fan_in(module)
            findings.append(
                self.finding(
                    severity=Severity.MEDIUM,
                    message=f"God module: imports {fo} modules (fan-in: {fi})",
                    suggestion=(
                        f"Split into smaller modules. Threshold: {self._god_module_threshold} imports"
                    ),
                    file=file.path,
                    line=1,
                    rule_id="ARC002",
                    category="architecture",
                )
            )

        if fo == 0 and self._graph.fan_in(module) == 0 and len(self._graph.nodes) > 1:
            findings.append(
                self.finding(
                    severity=Severity.INFO,
                    message="Isolated module: no imports and no dependents",
                    suggestion="Verify this module is intentionally standalone",
                    file=file.path,
                    line=1,
                    rule_id="ARC003",
                    category="architecture",
                )
            )

        if fo > 0 and self._graph.fan_in(module) == 0 and len(self._graph.nodes) > 1:
            findings.append(
                self.finding(
                    severity=Severity.LOW,
                    message=f"Leaf module: {module} is imported by nothing",
                    suggestion="Check if this module is dead code or only used at entry points",
                    file=file.path,
                    line=1,
                    rule_id="ARC004",
                    category="architecture",
                )
            )

        return findings

    def summary(self) -> str:
        """Return a summary of the full analysis. Call after all files analyzed."""
        return (
            f"Architecture: {len(self._graph.nodes)} modules, "
            f"{len(self._graph.find_cycles())} cycles, "
            f"{len(self._graph.find_god_modules(self._god_module_threshold))} god modules"
        )

    def get_config_schema(self) -> dict:
        return {
            "god_module_threshold": {
                "type": "integer",
                "default": 10,
                "description": "Max imports before a module is flagged as a god module",
            },
        }
