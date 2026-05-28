# Sentinel

**Autonomous code review bot** — built with sub-agents following the [Agent Development Lifecycle](https://blog.langchain.dev/the-agent-development-lifecycle/) (ADLC) by Harrison Chase.

Zero external dependencies. Pure Python stdlib.

## Quickstart

```bash
# Review a file
python -m sentinel.deploy.runner path/to/file.py

# Review a directory in parallel (agents run concurrently per file)
python -m sentinel.deploy.runner path/to/dir/ --workers 4

# JSON output
python -m sentinel.deploy.runner file.py --format json

# Disable specific agents
python -m sentinel.deploy.runner file.py --disable-agent security --disable-agent style

# Enable tracing with cost cap (Govern phase)
python -m sentinel.deploy.runner file.py -v --trace-dir ./traces --cost-cap 0.05

# Submit feedback for a finding (Monitor phase)
python -m sentinel.deploy.runner --feedback <finding_id> trace_20250101_120000.json --rating incorrect --comment "False positive"

# Start the web dashboard
python -m sentinel.monitor.dashboard --trace-dir ./traces --port 8080

# Run simulation engine (Test phase)
python -m sentinel.test.simulations
```

## Data Flow

```
                                ┌─────────────┐
                                │  CLI / User  │
                                └──────┬──────┘
                                       │ paths, flags
                                       v
                                ┌──────────────┐
                                │   runner.py   │
                                │   load_config │
                                └──────┬───────┘
                                       │ FileContext[]
                                       v
              ┌───────────────────────────────────────────┐
              │              Orchestrator                  │
              │                                            │
              │  ┌──────────────┐    ┌──────────────────┐  │
              │  │  CostTracker  │    │     Tracer       │  │
              │  │  (per-agent)  │    │  (events+metrics)│  │
              │  └──────┬───────┘    └────────┬─────────┘  │
              │         │                     │            │
              │         v                     v            │
              │  ┌────────────────────────────────────┐    │
              │  │       ThreadPoolExecutor            │    │
              │  │  ┌────────┐┌──────┐┌─────┐┌─────┐  │    │
              │  │  │static- ││secu- ││style││best-│ ...│    │
              │  │  │analysis││rity  ││     ││prac │  │    │
              │  │  └───┬────┘└──┬───┘└──┬──┘└──┬──┘  │    │
              │  └──────┼────────┼───────┼──────┼──────┘    │
              │         │        │       │      │           │
              │         v        v       v      v           │
              │         Finding[] (per agent)               │
              │                                            │
              └───────────────────────┬────────────────────┘
                                      │ AgentResult[]
                                      v
                            ┌──────────────────┐
                            │    SummaryAgent   │
                            │  (score + verdict)│
                            └────────┬─────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   │                 │                  │
                   v                 v                  v
            ┌──────────┐    ┌──────────────┐   ┌──────────────┐
            │  Report   │    │   Tracer     │   │  CostTracker  │
            │ (JSON/MD) │    │ (trace files)│   │  (cost line)  │
            └──────────┘    └──────┬───────┘   └──────────────┘
                                   │
                                   v
                          ┌────────────────────┐
                          │  feedback_trace_*.json
                          │  (POST /api/feedback)│
                          └────────┬───────────┘
                                   │
                                   v
                          ┌────────────────────┐
                          │  Dashboard (HTML)  │
                          │  /api/stats        │
                          │  /api/traces       │
                          │  /api/feedback     │
                          └────────────────────┘

► External inputs:  CLI args, --config .code-review.json, --feedback
► Storage:         trace_*.json, feedback_trace_*.json, .sentinel-profiles/
► Outputs:         stdout (MD/JSON), dashboard (HTTP), trace files
```

## Agents

| Agent | Rules | Checks |
|---|---|---|
| **static-analysis** | 9 | Cyclomatic complexity, line length, nesting depth, unused imports, trailing whitespace |
| **security** | 32 + secret scanner | eval/exec, pickle, SQLi, XSS, SSTI, hardcoded creds, JWT, AWS keys, weak crypto, XXE, and more |
| **style** | 6 | Import ordering, naming conventions (CapWords/snake_case), docstrings, magic numbers, is-vs-== |
| **best-practices** | 5 | Bare excepts, lambda assignments, mutable defaults, globals, type hints, context managers |
| **documentation** | 6 | Module/function/class docstrings, inline comment coverage |

## ADLC Phases

The project is organized around the five phases of the [Agent Development Lifecycle](https://blog.langchain.dev/the-agent-development-lifecycle/):

### Build

Agent source code, tools, and orchestration framework.

| Module | Files | Purpose |
|---|---|---|
| `sentinel/agents/` | `static_analysis.py`, `security.py`, `style.py`, `best_practices.py`, `documentation.py`, `summary.py` | 6 sub-agents — each has a self-contained `analyze()` method returning `list[Finding]` |
| `sentinel/core/` | `orchestrator.py`, `base_agent.py`, `context.py`, `types.py` | Orchestrator coordinates agents via two-level parallelism (file-level + agent-level), `BaseAgent` abstract class with `run()` lifecycle, `FileContext`/`ReviewReport`/`Finding` data models |
| `sentinel/tools/` | `ast_tools.py`, `config.py`, `git_tools.py`, `secrets_scanner.py` | AST complexity analysis, `.code-review.json` config loader, diff parsing, standalone secrets scanner (20+ patterns) |
| **Design** | | Zero external dependencies (pure stdlib). Agents are stateless and thread-safe. Parallelism via `ThreadPoolExecutor` with separate file and agent pools to avoid deadlock. |

```bash
# Run a review
python -m sentinel.deploy.runner path/to/file.py
```

### Test

Regression datasets, eval suite, simulation engine, and unit tests.

| Component | Files | Purpose |
|---|---|---|
| **Eval datasets** | `sentinel/test/fixtures/good_code.py`, `bad_code.py` | Known-good (4 findings) and known-bad (89 findings) fixtures for regression testing |
| **Eval runner** | `sentinel/test/evals.py` | Scores 100% when both datasets match expected finding counts |
| **Simulation engine** | `sentinel/test/simulations.py` | 3 multi-turn scenarios (bad→good, no-regression, severity improves), 6/6 steps |
| **Unit tests** | `tests/test_*.py` (14 files) | 268 tests covering all agents, tools, orchestrator, cost tracker, tracer, dashboard, context hub, registry |

```bash
python -m sentinel.test.evals
python -m sentinel.test.simulations
python -m unittest discover -s tests/ -q
```

### Deploy

CLI entry point and infrastructure for versioned configuration.

| Component | Files | Purpose |
|---|---|---|
| **CLI runner** | `sentinel/deploy/runner.py` | `main()` entry point — parses args, loads config, runs orchestrator, writes output. Supports `--format`, `--output`, `--disable-agent`, `--trace-dir`, `--verbose`, `--config`, `--cost-cap`, `--feedback`, `--workers` |
| **Context Hub** | `sentinel/govern/context_hub.py` | Versioned named profiles — `get/set/delete` with SHA-256 version tracking per entry, stored as JSON files |
| **Config** | `.code-review.json` | Thresholds (complexity 80, nesting 8, function length 80, params 12), suppress rules with fnmatch on rule_id/file, per-agent thresholds |

```bash
python -m sentinel.deploy.runner dir/ --workers 4 --format json -o report.json
python -m sentinel.deploy.runner file.py --disable-agent security
python -m sentinel.deploy.runner file.py --trace-dir ./traces --cost-cap 0.05
```

### Monitor

Observability — tracing, metrics, feedback collection, and a web dashboard.

| Component | Files | Purpose |
|---|---|---|
| **Tracer** | `sentinel/monitor/tracer.py` | Captures trace events (`run.started`, `run.completed`, `review.*`), metrics, feedback storage/export. Pluggable — can swap for OpenTelemetry, LangSmith |
| **Dashboard** | `sentinel/monitor/dashboard.py` | Self-contained web dashboard (stdlib `http.server`). Serves HTML/JS with bar charts, trend charts, trace table, feedback section. REST API: `/api/stats`, `/api/traces`, `/api/feedback` (POST) |
| **Feedback** | Via tracer + dashboard + CLI | `Feedback` dataclass in `core/types.py`. `Tracer.store_feedback()` writes `feedback_trace_*.json`. Dashboard loads and displays feedback entries. CLI `--feedback` flag submits human ratings |

```bash
python -m sentinel.monitor.dashboard --trace-dir ./traces --port 8080
python -m sentinel.deploy.runner --feedback <finding_id> trace_*.json --rating incorrect --comment "False positive"
```

### Govern

Cost governance, agent registry, and policy enforcement.

| Component | Files | Purpose |
|---|---|---|
| **CostTracker** | `sentinel/govern/cost.py` | Per-agent cost rates (static agents cost $0, LLM agents configurable), cost caps via `--cost-cap`, summary line in report. Thread-safe with reentrant lock |
| **AgentRegistry** | `sentinel/govern/registry.py` | `AgentRegistry.default()` registers all 6 agents with config schemas, `list_agents()`, `find_by_tag()`, `find_by_capability()`, discovery metadata |
| **Suppress rules** | `.code-review.json` + `runner.py` | fnmatch-based suppression on `rule_id` + `file` pattern, applied after review via `suppress_findings()` |
| **Audit** | Trace files + tracer | Every `run.started`/`run.completed`/`review.completed` event logged with duration, finding count, cost, errors — full JSON audit trail |

## Quality

```bash
ruff check sentinel/ tests/
ruff format --check sentinel/ tests/
ty check sentinel/
python -m unittest discover -s tests/ -q
python -m sentinel.test.evals
python -m sentinel.test.simulations
```

## License

MIT
