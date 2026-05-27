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

# Enable tracing (ADLC Monitor)
python -m sentinel.deploy.runner file.py -v --trace-dir ./traces

# Start the web dashboard
python -m sentinel.monitor.dashboard --trace-dir ./traces
```

## Agents

| Agent | Rules | Checks |
|---|---|---|
| **static-analysis** | 9 | Cyclomatic complexity, line length, nesting depth, unused imports, trailing whitespace |
| **security** | 32 + secret scanner | eval/exec, pickle, SQLi, XSS, SSTI, hardcoded creds, JWT, AWS keys, weak crypto, XXE, and more |
| **style** | 6 | Import ordering, naming conventions (CapWords/snake_case), docstrings, magic numbers, is-vs-== |
| **best-practices** | 5 | Bare excepts, lambda assignments, mutable defaults, globals, type hints, context managers |
| **documentation** | 1 | Module-level docstrings |

## ADLC Phases

| Phase | Implementation |
|---|---|
| **Build** | 5 sub-agents + orchestrator + AST tools (pure stdlib) |
| **Test** | Eval datasets (`test/fixtures/`), experiment runner, 196 unit tests |
| **Deploy** | CLI with `--format`, `--output`, `--disable-agent`, `--config`, `--trace-dir` |
| **Monitor** | Tracer + web dashboard with bar/trend charts, JSON API |
| **Govern** | `--disable-agent`, `suppress` rules via `.code-review.json`, JSON audit trails |

## Quality

```bash
ruff check sentinel/ tests/
ruff format --check sentinel/ tests/
ty check sentinel/
python -m unittest discover -s tests/ -q
python -m sentinel.test.evals
```

## License

MIT
