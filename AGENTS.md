# Code Review Bot — Development Reference

> **Python + JavaScript.** `.py` and `.js` files are discovered and analyzed. Other languages return empty results via `NullParser`. Add language support by implementing `BaseParser` and registering it in `ParserRegistry`.

## CRITICAL: Branching Rule

**NEVER push directly to `main`.** Always:
1. Create a feature branch: `git checkout -b feature/your-feature main`
2. Commit on the branch
3. Push the branch: `git push -u origin feature/your-feature`
4. Create a PR and get it reviewed before merging

Violating this rule breaks the CI pipeline and review process.

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
│   ├── architecture.py     # Import graph analysis: cycles, god modules, coupling
│   ├── refactor.py         # Refactor opportunity detection (composite score)
│   ├── risk_summary.py     # PR-level cross-file risk assessment (RSK001-005)
│   ├── execution_agent.py  # Hybrid tool + sandboxed code execution agent (decision policy, iterative fix)
│   ├── llm_review.py       # Optional LLM-powered review with RAG context retrieval
│   └── summary.py          # Compiles final verdict, severity breakdown, cost summary
├── parsers/             # <-- Language-agnostic parser abstraction
│   ├── base.py          # BaseParser ABC (15 methods for language-agnostic analysis)
│   ├── python.py        # PythonParser — full ast.* implementation
│   ├── javascript.py    # JavaScriptParser — regex/line-based heuristics
│   ├── null.py          # NullParser — safe empty defaults for unsupported languages
│   ├── models.py        # 11 typed dataclasses: FunctionLength, UnusedImport, etc.
│   └── __init__.py      # ParserRegistry + default_registry singleton
├── rag/
│   ├── vector_store.py     # TF-IDF vector store + cosine similarity (pure Python)
│   ├── knowledge_base.py   # Code chunking, CRUD for findings, JSON persistence
│   └── retriever.py        # Similarity search + RAG prompt builder for agents
├── tools/
│   ├── ast_tools.py        # Delegates to PythonParser (backward compat shim)
│   ├── import_graph.py     # AST-based import dependency graph builder (cycles, coupling, god modules)
│   ├── config.py           # .code-review.json loader with filter/suppress/matches helpers
│   ├── git_tools.py        # Diff parsing, language detection (20+ extensions)
│   ├── sandbox.py          # Secure Python execution sandbox (restricted exec, timeout, import allow-list)
│   ├── secrets_scanner.py  # Standalone secrets scanner (20+ patterns)
│   └── tool_registry.py    # Discoverable direct tools for the hybrid execution agent
├── reporting/
│   └── report.py           # Markdown and JSON report generators
├── monitor/
│   ├── tracer.py           # Trace events, metrics, feedback storage, JSON export (Monitor phase)
│   └── dashboard.py        # Web dashboard with feedback POST API and trend chart
├── govern/
│   ├── cost.py             # CostTracker — per-agent cost tracking with caps (Govern phase)
│   ├── context_hub.py      # ContextHub — versioned profiles for rules, policies, prompts (Deploy)
│   ├── registry.py         # AgentRegistry — discoverable agent info with config schemas (Govern)
│   └── rule_miner.py       # Offline knowledge base mining for new rule suggestions
├── test/
│   ├── evals.py            # Eval suite runner with pass/fail scoring
│   ├── simulations.py      # Simulation engine — multi-turn synthetic interaction testing
│   └── fixtures/
│       ├── good_code.py    # Known-good eval dataset
│       └── bad_code.py     # Known-bad eval dataset (89 findings across all agents)
└── deploy/
    └── runner.py           # CLI entry point with review + feedback + LLM submission
```

## ADLC Phase Mapping

| ADLC Phase | Implementation | Status |
|---|---|---|
| **Build** | 10 sub-agents (static-analysis, security, style, best-practices, documentation, architecture, refactor, summary) + optional (llm-review, execution-agent) + RAG (TF-IDF vector store, knowledge base, retriever) + risk-summary + orchestrator + tools (import-graph) + sandbox + tool registry + parsers (PythonParser, JavaScriptParser, NullParser) | ✅ Complete (architecture + refactor + risk-summary + import-graph added; parser abstraction layer with 3 parsers) |
| **Test** | `test/evals.py` (2 fixtures, 100% score), `test/simulations.py` (3 scenarios, 6/6 steps), 609 unit tests | ✅ Complete (JS parser, NullParser tests added) |
| **Deploy** | `deploy/runner.py` CLI with `--format`, `--output`, `--disable-agent`, `--trace-dir`, `--config`, `--cost-cap`, `--feedback`, `--workers`, `--llm-api-key`, `--llm-model`, `--rag-kb-dir`; `govern/context_hub.py` for versioned profiles | ✅ Complete (LLM + RAG flags added) |
| **Monitor** | `monitor/tracer.py` captures trace events + metrics + feedbacks; `monitor/dashboard.py` HTML/JSON dashboard with `/api/feedback` POST endpoint | ✅ Complete (feedback pipeline added) |
| **Govern** | `--disable-agent`, `suppress` rules, severity-weighted scoring, JSON audit trails; `govern/cost.py` cost caps; `govern/registry.py` agent discoverability (11 agents) | ✅ Complete (cost + registry added) |

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

# Enable LLM-powered review with RAG context
python -m sentinel.deploy.runner path/to/file.py --llm-api-key sk-... --llm-model gpt-4o-mini

# Persist and reuse RAG knowledge base
python -m sentinel.deploy.runner path/to/dir/ --llm-api-key sk-... --rag-kb-dir ./kb

# Custom sandbox timeout and retry limits
python -m sentinel.deploy.runner path/to/file.py --llm-api-key sk-... --sandbox-timeout 60 --sandbox-retries 5

# Disable execution agent but keep LLM review
python -m sentinel.deploy.runner path/to/file.py --llm-api-key sk-... --disable-agent execution

# Disable architecture or refactor agents
python -m sentinel.deploy.runner path/to/file.py --disable-agent architecture --disable-agent refactor

# Run rule miner on a knowledge base
python -m sentinel.govern.rule_miner --kb-dir ./kb

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
git config core.hooksPath .githooks
SKIP=lint,format,ty,secrets,coverage git commit -m "skip all hooks"
```

Expected: 100% on both good_code and bad_code fixtures, **609 tests passing**, 3/3 simulation scenarios passing, 85%+ coverage, zero ruff/ty errors.

## Hybrid Execution Agent

The execution agent (`sentinel/agents/execution_agent.py`) implements the **production hybrid agent pattern:**

1. **Decision policy** — routes between direct tools (simple lookups) and sandboxed Python code (multi-step/compositional)
2. **Sandboxed execution** — LLM generates Python code that uses injected tool functions, runs in restricted `Sandbox`
3. **Iterative fix loop** — on sandbox error, feeds traceback back to LLM, rewrites and re-executes (capped at `max_retries`)
4. **Direct tools** — exposed via `ToolRegistry` wrapping `sentinel/tools/` functions with auto-detected signatures
5. **Safety** — sandbox blocks `os`, `sys`, `subprocess`, `socket`, `ctypes`, `open`, `eval`, `exec`, `compile`; only allow-listed stdlib modules permitted

Key design: the execution agent complements (does not replace) the 7 deterministic static agents. It handles cross-cutting analysis that requires dynamic code, custom filtering, or tool composition.

## ADLC Gaps (All Resolved)

| Gap | Resolution |
|---|---|
| **Feedback Pipeline** (Monitor) | `Tracer.store_feedback()` + `export_feedback()` + dashboard `POST /api/feedback` + `--feedback` CLI flag |
| **Simulation Engine** (Test) | `sentinel/test/simulations.py` with 3 scenarios (bad→good, no regression, severity improves), 6/6 steps passing |
| **Cost Governance** (Govern) | `sentinel/govern/cost.py` — `CostTracker` with per-agent rates, cost caps, summary in report |
| **Context Hub** (Deploy) | `sentinel/govern/context_hub.py` — versioned named profiles with get/set/delete, SHA-256 version tracking |
| **Agent Registry** (Govern) | `sentinel/govern/registry.py` — `AgentRegistry.default()` with 7 agents, config schemas, tag/capability search |
| **RAG Knowledge Base** (Build) | `sentinel/rag/vector_store.py` (TF-IDF), `knowledge_base.py` (chunking + persistence), `retriever.py` (similarity search) |
| **LLM Review Agent** (Build) | `sentinel/agents/llm_review.py` — optional OpenAI-compatible agent with RAG context, wired via `--llm-api-key` |
| **Hybrid Execution Agent** (Build) | `sentinel/agents/execution_agent.py` — hybrid tool + sandboxed code execution with decision policy and iterative fix loop |
| **Secure Sandbox** (Build) | `sentinel/tools/sandbox.py` — restricted Python exec with import allow-list, timeout, stdout capture |
| **Tool Registry** (Build) | `sentinel/tools/tool_registry.py` — discoverable direct tools wrapping `sentinel/tools/` functions |
| **Import Graph Tool** (Build) | `sentinel/tools/import_graph.py` — AST-based import dependency graph builder with cycle detection, fan-in/out, god modules |
| **Architecture Agent** (Build) | `sentinel/agents/architecture.py` — deterministic import graph analysis: cycles (ARC001), god modules (ARC002), isolated (ARC003), leaf (ARC004) |
| **Refactor Agent** (Build) | `sentinel/agents/refactor.py` — deterministic composite score from complexity/length/params, REF001 (medium/high) + REF002 (critical) |
| **Risk Summary** (Build) | `sentinel/agents/risk_summary.py` — PR-level cross-file risk aggregation: concentration (RSK001-002), cross-cutting security (RSK003), architecture risk (RSK004), overall risk (RSK005) |
| **Rule Miner** (Govern) | `sentinel/govern/rule_miner.py` — offline knowledge base mining for new rule suggestions, invoked via `python -m sentinel.govern.rule_miner --kb-dir ./kb` |

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
- **RAG is pure Python** — TF-IDF vector store with cosine similarity, no external dependencies. Knowledge base persists as JSON files under `--rag-kb-dir`.
- **LLM agent is optional** — skipped entirely when `--llm-api-key` is not provided. Zero overhead when not in use.
- **Secrets scanner skips test files** in pre-commit hook to avoid false positives on fake API keys in tests.
