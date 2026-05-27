# Getting Started

## Prerequisites

- Python 3.9+
- No external dependencies required (pure stdlib)

## Quick Start

```bash
# Review a single file
python -m sentinel.deploy.runner path/to/file.py

# Review all Python files in a directory
python -m sentinel.deploy.runner path/to/dir/

# Install as a CLI command
pip install -e .
code-review-bot path/to/file.py
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

## Tracing

```bash
# Enable trace export (ADLC Monitor phase)
python -m sentinel.deploy.runner file.py -v --trace-dir ./traces
```

---

# Contributing

## Project Structure

```
sentinel/
├── core/           # Base agent, orchestrator, types, context
├── agents/         # Sub-agents (static analysis, security, style, etc.)
├── tools/          # AST parsing, git diff, language detection
├── reporting/      # Markdown and JSON report generators
├── monitor/        # Tracer for ADLC Monitor phase
├── test/
│   ├── evals.py    # ADLC Test phase: eval suite
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

2. Register in `core/orchestrator.py` — add to `ORCHESTRATOR_AGENTS` list
3. Add to `deploy/runner.py` — add to agent list and `--disable-agent` choices
4. Add test cases in `test/fixtures/bad_code.py` and `tests/test_agents.py`

## Adding a New Rule to an Existing Agent

1. Add a new `_check_*` method to the agent class
2. Call it from the `analyze()` method
3. Use a unique `rule_id` following the existing scheme (ST*, SEC*, STY*, BP*, DOC*)
4. Add a matching anti-pattern to `test/fixtures/bad_code.py`
5. Add a unit test in `tests/test_agents.py`

## Running Tests

```bash
# Unit tests
python -m unittest discover -s tests/ -v

# ADLC eval suite
python -m sentinel.test.evals

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

## Commit Conventions

- One change per commit (new agent, new rule, bug fix, docs)
- Prefix with the agent or module name: `static-analysis:`, `security:`, `docs:`, `tests:`
- Reference the rule ID when fixing a specific check

## Architecture Notes

- **No external dependencies** — keep it pure stdlib. Zero install friction.
- **Agents are independent** — each `analyze()` is self-contained. No shared mutable state.
- **Tracer is pluggable** — swap for OpenTelemetry, LangSmith, etc. by implementing `trace()`.
- **Eval datasets mirror production** — regressions are caught before deployment.
