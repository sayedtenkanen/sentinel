# Code Review Bot — Development Reference

## Project Structure

```
sentinel/
├── core/
│   ├── base_agent.py      # Abstract base for all agents (analyze + run lifecycle)
│   ├── context.py          # ReviewContext: files + config for a review session
│   ├── orchestrator.py     # Coordinates sub-agents, collects results, integrates tracer + cost tracker
│   └── types.py            # Data models: Finding, Severity, ReviewReport, TraceEvent, Feedback
├── agents/
│   ├── static_analysis.py  # Cyclomatic complexity, line length, nesting, unused imports, params
│   ├── security.py         # 32 security patterns (eval, pickle, SQLi, secrets, etc.)
│   ├── style.py            # Import order, naming conventions, docstrings, magic numbers
│   ├── best_practices.py   # Bare excepts, mutable defaults, globals, type hints, context mgrs
│   ├── documentation.py    # Module/function/class docstrings, comment coverage
│   └── summary.py          # Compiles final verdict, severity breakdown, cost summary
├── tools/
│   ├── ast_tools.py        # AST-based complexity, function length, unused import detection
│   ├── config.py           # .code-review.json loader with filter/suppress/matches helpers
│   ├── git_tools.py        # Diff parsing, language detection
│   └── secrets_scanner.py  # Standalone secrets scanner (20+ patterns)
├── reporting/
│   └── report.py           # Markdown and JSON report generators
├── monitor/
│   ├── tracer.py           # Trace events, metrics, feedback storage, JSON export (Monitor phase)
│   └── dashboard.py        # Web dashboard with feedback POST API and trend chart
├── govern/
│   ├── cost.py             # CostTracker — per-agent cost tracking with caps (Govern phase)
│   ├── context_hub.py      # ContextHub — versioned profiles for rules, policies, prompts (Deploy)
│   └── registry.py         # AgentRegistry — discoverable agent info with config schemas (Govern)
├── test/
│   ├── evals.py            # Eval suite runner with pass/fail scoring
│   ├── simulations.py      # Simulation engine — multi-turn synthetic interaction testing
│   └── fixtures/
│       ├── good_code.py    # Known-good eval dataset
│       └── bad_code.py     # Known-bad eval dataset (89 findings across all agents)
└── deploy/
    └── runner.py           # CLI entry point with review + feedback submission
```

## ADLC Phase Mapping

| ADLC Phase | Implementation | Status |
|---|---|---|
| **Build** | 5 sub-agents + documentation agent, orchestrator, tools, base framework | ✅ Complete |
| **Test** | `test/evals.py` (2 fixtures, 100% score), `test/simulations.py` (3 scenarios, 6/6 steps), 264 unit tests | ✅ Complete (multi-turn sims added) |
| **Deploy** | `deploy/runner.py` CLI with `--format`, `--output`, `--disable-agent`, `--trace-dir`, `--config`, `--cost-cap`, `--feedback`; `govern/context_hub.py` for versioned profiles | ✅ Complete (context hub added) |
| **Monitor** | `monitor/tracer.py` captures trace events + metrics + feedbacks; `monitor/dashboard.py` HTML/JSON dashboard with `/api/feedback` POST endpoint | ✅ Complete (feedback pipeline added) |
| **Govern** | `--disable-agent`, `suppress` rules, severity-weighted scoring, JSON audit trails; `govern/cost.py` cost caps; `govern/registry.py` agent discoverability | ✅ Complete (cost + registry added) |

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

# With cost cap (in dollars)
python -m sentinel.deploy.runner path/to/file.py --cost-cap 0.05

# Parallel agent processing
python -m sentinel.deploy.runner path/to/dir/ --workers 4

# Write to file
python -m sentinel.deploy.runner path/to/file.py -o report.md

# Submit feedback for a finding (flag as correct/incorrect)
python -m sentinel.deploy.runner --feedback <finding_id> trace_20250101_120000.json --rating incorrect --comment "False positive"

# Dashboard
python -m sentinel.monitor.dashboard --port 8080 --trace-dir ./traces

# Simulation engine
python -m sentinel.test.simulations
```

## Running Tests & Quality Checks

```bash
# Run eval suite (ADLC Test phase)
python -m sentinel.test.evals

# Run simulation engine (ADLC Test phase — multi-turn)
python -m sentinel.test.simulations

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

Expected: 100% on both good_code and bad_code fixtures, **264 tests passing**, 3/3 simulation scenarios passing, 85%+ coverage, zero ruff/ty errors.

## ADLC Gaps (All Resolved)

| Gap | Resolution |
|---|---|
| **Feedback Pipeline** (Monitor) | `Tracer.store_feedback()` + `export_feedback()` + dashboard `POST /api/feedback` + `--feedback` CLI flag |
| **Simulation Engine** (Test) | `sentinel/test/simulations.py` with 3 scenarios (bad→good, no regression, severity improves), 6/6 steps passing |
| **Cost Governance** (Govern) | `sentinel/govern/cost.py` — `CostTracker` with per-agent rates, cost caps, summary in report |
| **Context Hub** (Deploy) | `sentinel/govern/context_hub.py` — versioned named profiles with get/set/delete, SHA-256 version tracking |
| **Agent Registry** (Govern) | `sentinel/govern/registry.py` — `AgentRegistry.default()` with 6 agents, config schemas, tag/capability search |

## Key Design Decisions

- **No external dependencies** — pure Python stdlib (AST, re, json, dataclasses, http.server). Zero install friction.
- **Agents are independent** — each `analyze()` is self-contained. Easy to add/remove/reorder.
- **Tracer is pluggable** — can be swapped for OpenTelemetry, LangSmith, etc.
- **CostTracker is wired through orchestrator** — automatically tracks duration per agent, supports custom rates for LLM agents.
- **Feedback stored as separate JSON files** (`feedback_trace_*.json`) alongside trace files, loaded by dashboard.
- **Context Hub profiles** stored as `{base_dir}/{name}.json` with SHA-256 version hashes per entry.
- **Simulation engine** allows multi-step scenarios with finding range expectations and rule ID checks.
- **Agent Registry** provides a static `default()` with all built-in agents and their config schemas.
- **Eval datasets mirror production** — good_code and bad_code fixtures serve as regression dataset per the ADLC article: *"Datasets are how teams preserve what they learn."*
- **Suppress rules** support fnmatch wildcards on both `rule` and `pattern` fields in `.code-review.json`.
- **Parallel processing** — `--workers N` runs agents concurrently via `ThreadPoolExecutor`. Agents are stateless and thread-safe. Falls back to sequential when `max_workers` is `None`. Best suited when agents perform I/O or release the GIL (regex/AST parsing).
