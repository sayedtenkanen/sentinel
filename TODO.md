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

---

## Sentinel Memory — Dreaming-Style Memory System

> Evaluation before features. Build measurement first.

### Architecture

```
Stage 0: Evaluation Framework    ← build FIRST
    ↓
Stage 1: Review Session → Raw Events
    ↓
Stage 2: Extraction → Memory Candidates
    ↓
Stage 3: Validation → Verified Memories
    ↓
Stage 4: Conflict Resolution → Resolved Memories
    ↓
Stage 5: Synthesis → Memory Store
    ↓
Stage 6: Retrieval → Agent Context
    ↓
    (loop back to Stage 0 for measurement)
```

### Stage 0: Evaluation Framework

**Metrics Data Models:**

```python
@dataclass
class RunMetrics:
    run_id: str
    timestamp: str
    files_reviewed: int
    findings_total: int
    agent_latencies: dict[str, float]  # agent_name → ms
    token_cost: float
    duration_ms: float
    memory_retrieved: bool
    memory_count: int

@dataclass
class MemoryMetrics:
    run_id: str
    memory_precision: float   # correct retrievals / total retrievals
    memory_recall: float      # useful memories / total available
    contradiction_count: int
    stale_memory_count: int
    synthesis_count: int

@dataclass
class UserMetrics:
    run_id: str
    followup_reduction: float
    feedback_accuracy: float
    suppression_quality: float
```

**Storage:** JSON files under `--metrics-dir`

**CLI:** `python -m sentinel.deploy.runner path/to/file.py --metrics-dir ./metrics`

### Stage 1: Review Session → Raw Events

```python
@dataclass
class ReviewEvent:
    file_path: str
    finding_id: str
    rule_id: str
    severity: str
    agent: str
    timestamp: str
    code_content: str
    language: str
    file_context: str   # tests/, src/, docs/

@dataclass
class FeedbackEvent:
    finding_id: str
    rating: str         # correct, incorrect, unsure
    comment: str
    user: str | None
    timestamp: str
```

**Integration:** Already captured by `Tracer`. No new code needed.

### Stage 2: Extraction → Memory Candidates

| Strategy | Input | Output | Threshold |
|---|---|---|---|
| Pattern mining | 3+ feedbacks, same rule, same outcome | MemoryCandidate | confidence > 0.7 |
| Preference inference | Consistent rating patterns | MemoryCandidate | confidence > 0.6 |
| Context observation | File paths, imports, structure | MemoryCandidate | confidence > 0.8 |

```python
@dataclass
class MemoryCandidate:
    id: str
    type: str           # rule, preference, context, temporal
    content: dict
    evidence: list[str]
    confidence: float
    extracted_at: str
    source: str
```

### Stage 3: Validation → Verified Memories

| Check | Logic | Failure Action |
|---|---|---|
| Pattern stability | Pattern still exists in codebase? | Requeue |
| Sample size | Confidence > 0.6? | Discard |
| Consistency | Contradicts existing memory? | Send to conflict resolution |
| Freshness | Extracted within 30 days? | Discard |

### Stage 4: Conflict Resolution → Resolved Memories

| Conflict | Strategy |
|---|---|
| User preference vs. global rule | User wins |
| Contradictory preferences | Latest wins |
| Memory vs. current reality | Current reality wins |
| Stale memory vs. fresh observation | Fresh wins |

### Stage 5: Synthesis → Memory Store

```python
@dataclass
class Memory:
    id: str
    type: str           # rule, preference, context
    content: dict
    confidence: float
    created_at: str
    last_used_at: str
    expires_at: str | None
    source: str
    tags: list[str]

class MemoryStore:
    def insert(self, memory: Memory) -> None: ...
    def query(self, tags: list[str] | None = None) -> list[Memory]: ...
    def update(self, memory_id: str, updates: dict) -> None: ...
    def delete(self, memory_id: str) -> None: ...
    def list_all(self) -> list[Memory]: ...
```

**Storage:** JSON file `--memory-dir/memory.json`

### Stage 6: Retrieval → Agent Context

```
Review Context (files, language)
    ↓
Intent Detection (what memories are relevant?)
    ↓
Memory Retrieval (query store by tags + type)
    ↓
Context Compression (summarize if too many)
    ↓
Agent Prompt Injection (append to context)
```

### Temporal Logic

| Memory Type | Half-life | Archive after |
|---|---|---|
| User preference | Never | Never |
| Project context | 90 days | 180 days |
| Finding pattern | 30 days | 60 days |
| Temporal fact | 14 days | 30 days |

### Sentinel Memory Implementation Steps

| Step | Phase | What | Deliverable |
|---|---|---|---|
| 1 | 0A | Metrics data models | `sentinel/memory/metrics.py` |
| 2 | 0B | Wire metrics into Tracer | Update `sentinel/monitor/tracer.py` |
| 3 | 0C | Baseline measurement | Run on fixtures, store baseline |
| 4 | 0D | Metrics CLI | `--metrics-dir` flag on runner |
| 5 | 1A | Memory store | `sentinel/memory/store.py` |
| 6 | 1B | Memory data models | `sentinel/memory/models.py` |
| 7 | 1C | Store CRUD | Unit tests for store |
| 8 | 2A | Memory retriever | `sentinel/memory/retriever.py` |
| 9 | 2B | Retriever integration | Wire into orchestrator |
| 10 | 3A | Feedback extractor | `sentinel/memory/extractor.py` |
| 11 | 3B | Context extractor | File observation logic |
| 12 | 3C | Synthesizer | Combine memories into rules |
| 13 | 4A | Validator | `sentinel/memory/validator.py` |
| 14 | 4B | Conflict resolver | `sentinel/memory/conflict.py` |
| 15 | 5A | Temporal logic | `sentinel/memory/temporal.py` |
| 16 | 5B | Consolidation job | Background synthesis |
| 17 | 0X | Memory evaluation | Precision/recall metrics |
| 18 | 0Y | A/B framework | Compare with/without memory |

### Sentinel Memory File Structure

```
sentinel/memory/
├── metrics.py       # RunMetrics, MemoryMetrics, UserMetrics
├── models.py        # Memory, MemoryCandidate, ReviewEvent, FeedbackEvent
├── store.py         # MemoryStore (JSON-backed)
├── retriever.py     # Context-aware memory retrieval
├── extractor.py     # Pattern mining from feedback
├── validator.py     # Verify patterns against codebase
├── conflict.py      # Resolve contradictory memories
├── synthesizer.py   # Combine related memories
├── temporal.py      # Aging, decay, expiration
├── eval.py          # Evaluation metrics
└── __init__.py      # Public API
```
