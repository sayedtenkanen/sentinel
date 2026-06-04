# Sentinel — Project Roadmap

## ✅ Complete

- [x] **Phase 1: Parser abstraction** — `BaseParser` ABC (15 methods), `PythonParser` (full `ast.*`), `ParserRegistry`
- [x] **Phase 2: Typed dataclass models** — 11 dataclasses replacing loose dicts (`FunctionLength`, `UnusedImport`, etc.)
- [x] **Phase 3: End-to-end wiring** — agents resolve parser per-file, `NullParser` fallback, `FileContext.language` set by runner
- [x] **JavaScriptParser** — regex/line-based heuristics for JS/TS/JSX/TSX
- [x] **JS + NullParser tests** — 39 new tests (609 total), 100% evals, 6/6 sims
- [x] **10 sub-agents**: static-analysis, security, style, best-practices, documentation, architecture, refactor, risk-summary, llm-review, execution
- [x] **Hybrid execution agent** — decision policy + sandboxed code execution + iterative fix loop
- [x] **Secure sandbox** — restricted Python exec with import allow-list, timeout
- [x] **Tool registry** — discoverable direct tools for the hybrid agent
- [x] **RAG** — TF-IDF vector store, knowledge base, retriever
- [x] **Import graph** — cycle detection, fan-in/out, god modules
- [x] **Rule miner** — offline knowledge base mining for new rule suggestions
- [x] **CLI** — `--format`, `--output`, `--disable-agent`, `--trace-dir`, `--config`, `--cost-cap`, `--feedback`, `--workers`, `--llm-api-key`, `--llm-model`, `--rag-kb-dir`, `--sandbox-timeout`, `--sandbox-retries`
- [x] **Dashboard** — web UI with stats, traces, feedback API
- [x] **Feedback pipeline** — store, export, CLI submission
- [x] **Cost governance** — per-agent cost caps
- [x] **Context hub** — versioned named profiles
- [x] **Agent registry** — discoverable agent info with config schemas
- [x] **CI** — GitHub Actions: ruff, ty, secrets scan, 609 tests, evals, simulations, sentinel review
- [x] **Pre-commit hooks** — ruff, ty, secrets scan, coverage
- [x] **Simulation engine** — 3 multi-turn scenarios
- [x] **Eval datasets** — good_code (4 findings) + bad_code (89 findings)

## 📋 Next Up

### Language Support
- [ ] **Go parser** — regex/line-based for `.go` files
- [ ] **Rust parser** — regex/line-based for `.rs` files
- [ ] **PythonParser: async functions** — handle `AsyncFunctionDef` in `find_mutable_defaults` and `find_missing_type_hints`

### Quality & Coverage
- [ ] **More JS parser tests** — edge cases, TSX/JSX, async/await, nested arrow functions
- [ ] **Integration tests** — run sentinel on fixtures, validate exact finding output
- [ ] **Property-based tests** — generate random code, verify parsers don't crash

### Architecture
- [ ] **Per-file parser resolution without caching** — agents should not cache parser on `self` for multi-language sessions
- [ ] **Agent-level language filtering** — some agents (architecture) are Python-only; make language requirements declarative
- [ ] **Parser performance benchmarks** — measure `compute_complexity`, `find_function_lengths` against large files

### Governance
- [ ] **Plugin/entry-point discovery** — discover parsers via `importlib.metadata` entry points
- [ ] **Configurable severity per rule** — allow `.code-review.json` to override severity levels
- [ ] **Webhook integration** — post review results to Slack, Discord, GitHub check runs

### Documentation
- [ ] **API docs** — docstrings for all public classes/methods
- [ ] **Architecture decision records** — ADRs for parser abstraction, hybrid execution agent
- [ ] **Example configs** — `.code-review.json` samples for monorepo, microservices, etc.
