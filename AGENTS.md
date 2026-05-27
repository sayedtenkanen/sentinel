# Code Review Bot — Development Reference

## Project Structure

```
sentinel/
├── core/
│   ├── base_agent.py      # Abstract base for all agents (analyze + run lifecycle)
│   ├── context.py          # ReviewContext: files + config for a review session
│   ├── orchestrator.py     # Coordinates sub-agents, collects results, integrates tracer
│   └── types.py            # Data models: Finding, Severity, ReviewReport, TraceEvent
├── agents/
│   ├── static_analysis.py  # Cyclomatic complexity, line length, nesting, unused imports
│   ├── security.py         # 17 security patterns (eval, pickle, SQLi, secrets, etc.)
│   ├── style.py            # Import order, naming conventions, docstrings, magic numbers
│   ├── best_practices.py   # Bare excepts, mutable defaults, globals, type hints, context mgrs
│   └── summary.py          # Compiles final verdict and severity breakdown
├── tools/
│   ├── ast_tools.py        # AST-based complexity, function length, unused import detection
│   └── git_tools.py        # Diff parsing, language detection
├── reporting/
│   └── report.py           # Markdown and JSON report generators
├── monitor/
│   └── tracer.py           # Trace events, metrics, JSON export (ADLC Monitor phase)
├── test/
│   ├── evals.py            # Eval suite runner with pass/fail scoring
│   └── fixtures/
│       ├── good_code.py    # Known-good eval dataset
│       └── bad_code.py     # Known-bad eval dataset
└── deploy/
    └── runner.py           # CLI entry point
```

## ADLC Phase Mapping

| ADLC Phase | Implementation | Gaps |
|---|---|---|
| **Build** | Sub-agents (5), orchestrator, tools, base framework | No runtime/state persistence — agents are stateless, single-pass |
| **Test** | `test/evals.py`, fixtures, experiment runner, 196 unit tests | **No multi-turn simulations** — evals are single-pass, no synthetic interaction testing |
| **Deploy** | `deploy/runner.py` CLI with `--format`, `--output`, `--disable-agent`, `--trace-dir` | No durable execution, no sandbox, no context hub |
| **Monitor** | `monitor/tracer.py` captures trace events; `monitor/dashboard.py` HTML/JSON dashboard | **No feedback pipeline** — no human/LLM feedback stored alongside traces. No LLM-as-judge signals |
| **Govern** | `--disable-agent`, `suppress` rules, severity-weighted scoring, JSON audit trails | **No cost tracking**, no agent discoverability registry |

## Known ADLC Gaps (Future Work)

Priority-ordered gaps from the ADLC article by Harrison Chase:

1. **Feedback Pipeline** (Monitor) — Store human + LLM feedback alongside traces. ADLC: *"store feedback with those traces."* Would enable: flagging false positives, marking findings as reviewed, and feeding real-world signal back into eval datasets.

2. **Simulation Engine** (Test) — Multi-turn synthetic interactions for regression testing agents. ADLC: *"multi-turn evals and simulated end-to-end interactions."* Our fixtures are single-pass static files.

3. **Cost Governance** (Govern) — Track and cap per-review cost. ADLC: *"track and manage spend through budgets, usage monitoring, alerts."* Less critical for static analysis, but would matter if integrating LLM-based reviewers.

4. **Context Hub** (Deploy) — Versioned, editable storage for review rules, suppression policies, and agent prompts. ADLC: *"store, version, review, and update the non-code parts of the agent."*

5. **Agent Registry** (Govern) — Discoverability for agents/configs. ADLC: *"reusable assets — prompts, skills, tools, retrieval sources, policies."* Would let teams share and compose review profiles.

## Build Steps

1. Created project structure with `core/`, `agents/`, `tools/`, `reporting/`, `monitor/`, `test/`, `deploy/`
2. Defined shared types: `Severity`, `Finding`, `AgentResult`, `ReviewReport`, `TraceEvent`
3. Built `BaseAgent` abstract class with `analyze()` + `run()` lifecycle (timing, error handling, tracing)
4. Built 4 sub-agents:
   - **StaticAnalysis**: complexity (cyclomatic), function length, line length, nesting, unused imports, trailing whitespace
   - **Security**: 17 regex patterns (eval, exec, pickle, SQLi, shell injection, hardcoded creds, etc.) with severity tiering
   - **Style**: import order grouping, CapWords/snake_case validation, docstrings, magic numbers, is-vs-== checks
   - **BestPractices**: bare excepts, lambda assignments, mutable defaults, globals, type hints, context manager enforcement
5. Built `Orchestrator` to fan out reviews to all agents and collect results
6. Built AST analysis tools for complexity/import analysis
7. Built `Tracer` for ADLC Monitor phase — captures per-agent trace events with duration, errors, metadata
8. Built `report.py` for markdown and JSON report generation
9. Built `runner.py` CLI with argument parsing
10. Built eval fixtures (`good_code.py`, `bad_code.py`) and `evals.py` test runner
11. Fixed misplaced `import re` in best_practices.py, fixed `startswith` and regex edge cases for inline comments

## CLI Usage

```bash
# Review a single file
python -m sentinel.deploy.runner path/to/file.py

# Review a directory
python -m sentinel.deploy.runner path/to/dir/

# JSON output
python -m sentinel.deploy.runner path/to/file.py --format json

# Disable specific agents
python -m sentinel.deploy.runner path/to/file.py --disable-agent style --disable-agent security

# Verbose mode with trace export
python -m sentinel.deploy.runner path/to/file.py -v --trace-dir ./traces

# Write to file
python -m sentinel.deploy.runner path/to/file.py -o report.md
```

## Running Tests & Quality Checks

```bash
# Run eval suite (ADLC Test phase)
python -m sentinel.test.evals

# Run all unit tests
python -m unittest discover -s tests/ -q

# Ruff linting
python -m ruff check sentinel/ tests/

# Ruff formatting (check)
python -m ruff format --check sentinel/ tests/

# Ruff formatting (apply)
python -m ruff format sentinel/ tests/

# Ty type checking (from Astral, ~10-100x faster than mypy)
python -m ty check sentinel/

# Coverage
pip install coverage
python -m coverage run -m unittest discover -s tests/ -q
python -m coverage report --omit="sentinel/test/*"

# Secrets scan
python -m sentinel.tools.secrets_scanner --recursive sentinel/

# Pre-commit hook (auto-runs on git commit)
SKIP=ty,secrets git commit -m "skips type check and secrets scan"
```

Expected: 100% on both good_code and bad_code fixtures, 179+ tests passing, 85%+ coverage, zero ruff/ty errors.

## Key Design Decisions

- **No external dependencies** — pure Python stdlib (AST, re, json, dataclasses). Zero install friction.
- **Agents are independent** — each `analyze()` is self-contained. Easy to add/remove/reorder.
- **Tracer is pluggable** — can be swapped for OpenTelemetry, LangSmith, etc.
- **Eval datasets mirror production** — good_code and bad_code fixtures serve as regression dataset per the ADLC article: *"Datasets are how teams preserve what they learn."*
