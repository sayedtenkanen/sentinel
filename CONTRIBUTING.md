# Quick Start

```bash
# Review a single file
python -m sentinel.deploy.runner path/to/file.py

# Review all Python files in a directory
python -m sentinel.deploy.runner path/to/dir/

# Install as a CLI command
pip install -e .
sentinel path/to/file.py
```

## Output Formats

```bash
# Markdown (default)
python -m sentinel.deploy.runner file.py

# JSON
python -m sentinel.deploy.runner file.py --format json

# Write to file
python -m sentinel.deploy.runner file.py -o report.md
```

## Agent Control

```bash
# Disable specific agents
python -m sentinel.deploy.runner file.py --disable-agent security --disable-agent style

# Available agents: static-analysis, security, style, best-practices, documentation
```

## Tracing & Feedback

```bash
# Enable trace export
python -m sentinel.deploy.runner file.py -v --trace-dir ./traces

# With cost cap
python -m sentinel.deploy.runner file.py --cost-cap 0.05

# Submit feedback on a finding
python -m sentinel.deploy.runner --feedback <finding_id> trace_20250101_120000.json --rating incorrect --comment "Wrong"

# Start dashboard
python -m sentinel.monitor.dashboard --port 8080 --trace-dir ./traces
```

---

# Contributing

## Project Structure

```
sentinel/
├── core/           # Base agent, orchestrator, types, context
├── agents/         # Sub-agents (static analysis, security, style, etc.)
├── tools/          # AST parsing, git diff, config loader, secrets scanner
├── reporting/      # Markdown and JSON report generators
├── monitor/        # Tracer + Dashboard (Monitor phase)
├── govern/         # Cost tracker, context hub, agent registry (Govern/Deploy)
├── test/
│   ├── evals.py    # ADLC Test phase: eval suite
│   ├── simulations.py  # Multi-turn synthetic interaction tests
│   └── fixtures/   # good_code.py + bad_code.py regression datasets
└── deploy/         # CLI runner
```

## Adding a New Agent

1. Create `sentinel/agents/your_agent.py`:

```python
from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity


class YourAgent(BaseAgent):
    def __init__(self, enabled: bool = True):
        super().__init__(name="your-agent", enabled=enabled)

    def analyze(self, file: FileContext) -> list[Finding]:
        findings = []
        # Your analysis logic here
        return findings
```

2. Register in `sentinel/govern/registry.py` — add to `AgentRegistry.default()`
3. Add to `sentinel/deploy/runner.py` — add to `_setup_agents()` and `--disable-agent` choices
4. Add test cases in `test/fixtures/bad_code.py` and `tests/test_agents.py`

## Adding a New Rule to an Existing Agent

1. Add a new `_check_*` method to the agent class
2. Call it from the `analyze()` method
3. Use a unique `rule_id` following the existing scheme (ST*, SEC*, STY*, BP*, DOC*)
4. Add a matching anti-pattern to `test/fixtures/bad_code.py`
5. Add a unit test in `tests/test_agents.py`

## Running Tests

```bash
# Unit tests (264 total)
python -m unittest discover -s tests/ -v

# ADLC eval suite
python -m sentinel.test.evals

# Simulation engine (3 scenarios, 6 steps)
python -m sentinel.test.simulations

# Coverage
pip install coverage
python -m coverage run -m unittest discover -s tests/
python -m coverage report --omit="sentinel/test/*"
```

## Eval Datasets

The `test/fixtures/` directory contains two critical files:

- **`good_code.py`** — Known-good code that should produce few findings (prevents regressions)
- **`bad_code.py`** — Known-bad code with intentional issues (validates detection works)

When adding a new rule, add matching examples to both files. This is the ADLC Test phase: *"Datasets are how teams preserve what they learn."*

## Simulation Scenarios

The simulation engine (`sentinel/test/simulations.py`) runs 3 multi-turn scenarios:

1. **Bad to Good** — review bad_code.py → 89 findings, then good_code.py → 4 findings
2. **No Regression** — clean code → 2 findings, add eval() → 3 findings including SEC003
3. **Severity Improves** — critical code → 5 findings, fixed version → 1 low finding

Add new scenarios via `DEFAULT_SCENARIOS` in `simulations.py`.

## Commit Conventions

- One change per commit (new agent, new rule, bug fix, docs)
- Prefix with the agent or module name: `static-analysis:`, `security:`, `docs:`, `tests:`
- Reference the rule ID when fixing a specific check

## Architecture Notes

- **No external dependencies** — keep it pure stdlib. Zero install friction.
- **Agents are independent** — each `analyze()` is self-contained. No shared mutable state.
- **Tracer is pluggable** — swap for OpenTelemetry, LangSmith, etc. by implementing `trace()`.
- **CostTracker** — wired through orchestrator, supports per-agent rates for LLM agents.
- **Feedback** — stored as `feedback_trace_*.json` alongside trace files, consumed by dashboard.
- **Context Hub** — versioned profiles stored as JSON with SHA-256 hashes per entry.
- **Eval datasets mirror production** — regressions are caught before deployment.
