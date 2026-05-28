# Sentinel

**Autonomous code review bot** — built with sub-agents following the [Agent Development Lifecycle](https://blog.langchain.dev/the-agent-development-lifecycle/) (ADLC) by Harrison Chase.

Zero external dependencies. Pure Python stdlib.

## Quickstart

```bash
# Review a file
python -m sentinel.deploy.runner path/to/file.py

# Review a directory
python -m sentinel.deploy.runner path/to/dir/

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

## Agents

| Agent | Rules | Checks |
|---|---|---|
| **static-analysis** | 9 | Cyclomatic complexity, line length, nesting depth, unused imports, trailing whitespace |
| **security** | 32 + secret scanner | eval/exec, pickle, SQLi, XSS, SSTI, hardcoded creds, JWT, AWS keys, weak crypto, XXE, and more |
| **style** | 6 | Import ordering, naming conventions (CapWords/snake_case), docstrings, magic numbers, is-vs-== |
| **best-practices** | 5 | Bare excepts, lambda assignments, mutable defaults, globals, type hints, context managers |
| **documentation** | 6 | Module/function/class docstrings, inline comment coverage |

## ADLC Phases

| Phase | Implementation |
|---|---|
| **Build** | 5 sub-agents + documentation agent + orchestrator + AST tools (pure stdlib) |
| **Test** | Eval datasets (`test/fixtures/`), experiment runner, simulation engine (6/6 steps), **264 unit tests** |
| **Deploy** | CLI with `--format`, `--output`, `--disable-agent`, `--config`, `--trace-dir`, `--cost-cap`, `--feedback`; Context Hub for versioned profiles |
| **Monitor** | Tracer + web dashboard with bar/trend charts, JSON API, **`POST /api/feedback`** endpoint |
| **Govern** | Cost tracking with caps, agent registry with config schemas, suppress rules via `.code-review.json`, JSON audit trails |

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
