# Final Code Review — Remora System

**Date:** 2026-03-02
**Scope:** Three codebases treated as one system
**Reviewer:** Automated comprehensive review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Flow Analysis](#3-data-flow-analysis)
4. [Module-Level Singleton Issue](#4-module-level-singleton-issue)
5. [Dual Event Type Systems](#5-dual-event-type-systems)
6. [Three SQLite Databases](#6-three-sqlite-databases)
7. [Code Duplication Between Repos](#7-code-duplication-between-repos)
8. [Two Runner Paths](#8-two-runner-paths)
9. [Thread Safety & Concurrency](#9-thread-safety--concurrency)
10. [Error Handling Patterns](#10-error-handling-patterns)
11. [Service Layer Analysis](#11-service-layer-analysis)
12. [UI Component System](#12-ui-component-system)
13. [Testing Coverage Analysis](#13-testing-coverage-analysis)
14. [Import & Dependency Issues](#14-import--dependency-issues)
15. [Dead Code & Unused Exports](#15-dead-code--unused-exports)
16. [Integration Risk Assessment](#16-integration-risk-assessment)
17. [Recommendations](#17-recommendations)

---

## 1. Executive Summary

### System Identity

Remora is an **event-sourced code intelligence system** that attaches AI agents to individual code nodes (functions, classes, modules). It runs as an LSP server inside Neovim, with a companion browser-based graph viewer showing agent state in real time. A separate CLI mode (`swarm`) enables headless agent execution.

### Codebase Metrics

| Codebase | Language | Python | Lines (approx.) | Test files |
|----------|----------|--------|-----------------|------------|
| Remora library | Python | 3.13 | ~7,500 | 80+ |
| remora_demo/ (in library repo) | Python | 3.13 | ~2,000 | 0 |
| Frontend (standalone repo) | Python | 3.14 | ~3,500 | 179 tests passing |

### Finding Summary

| Severity | Count | Key findings |
|----------|-------|-------------|
| **Critical** | 2 | Module-level singleton with `event_store=None`; dual event type systems with name collisions |
| **High** | 4 | Three separate SQLite databases; code duplication across repos; dead executor branch in runner; thread safety gaps |
| **Medium** | 5 | Broad error swallowing; `push_command()` not thread-locked; ConfigError shadow import; heavyweight dependency list; missing integration tests between repos |
| **Low** | 3 | Commented-out code in pyproject.toml; UI components tightly coupled to HTML strings; some unused public API exports |

### Overall Assessment

The system demonstrates a well-thought-out architecture for AI-augmented code editing. Event sourcing with SQLite persistence is a sound choice. The graph viewer is well-tested (179 tests, all passing). The core library has extensive test infrastructure.

The primary risks are at the **integration boundaries**: the module-level singleton pattern forces fragile initialization ordering, the dual event type system creates conversion overhead and name collision hazards, and code duplication between repos will inevitably drift. The three separate SQLite databases sharing the same file with different connection objects and locking strategies is the most operationally risky pattern.

---

## 2. Architecture Overview

### Three Codebases, One System

```
┌──────────────────────────────────────────────────────────────────┐
│                     Neovim (Editor)                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Remora LSP Server (Python 3.13)                           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────┐               │  │
│  │  │ Handlers │  │ Runner   │  │ EventStore │               │  │
│  │  │(doc,cmd, │  │(AgentRun,│  │(SQLite,    │               │  │
│  │  │ hover,..)│  │ LLMClient│  │ events+    │               │  │
│  │  └──────────┘  │ ToolLoop)│  │ nodes)     │               │  │
│  │                └──────────┘  └─────┬──────┘               │  │
│  │  ┌──────────┐  ┌──────────┐        │                      │  │
│  │  │ RemoraDB │  │ Watcher  │        │                      │  │
│  │  │(edges,   │  │(AST,tree │        │ .remora/indexer.db   │  │
│  │  │ proposals│  │ -sitter) │        │ (shared SQLite file) │  │
│  │  │ cmds)    │  └──────────┘        │                      │  │
│  │  └────┬─────┘                      │                      │  │
│  └───────┼────────────────────────────┼──────────────────────┘  │
└──────────┼────────────────────────────┼──────────────────────────┘
           │                            │
           │   SQLite file reads        │
           ▼                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Graph Viewer (Python 3.14 + Stario)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ bridge.py│  │ state.py │  │ layout.py│  │  svg.py  │        │
│  │ DB→Relay │  │GraphState│  │ Force-   │  │ SVG elem │        │
│  │ polling  │  │(SQLite   │  │ directed │  │ builders │        │
│  │          │  │ reader)  │  │ layout   │  │          │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌─────────────────────────────────────┐          │
│  │  app.py  │  │  views/ (shell, graph, sidebar, sse)│          │
│  │ Stario   │  │  return plain HTML/SVG strings      │          │
│  │ routes   │  └─────────────────────────────────────┘          │
│  └──────────┘                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Process Model

The system runs as **two separate OS processes**:

1. **LSP Server** (Python 3.13) — Launched by Neovim. Owns all writes to `.remora/indexer.db`. Contains EventStore, RemoraDB, AgentRunner, ASTWatcher.
2. **Graph Viewer** (Python 3.14) — Launched separately via `launch.sh`. Read-only SQLite access to the same `.remora/indexer.db`. Polls for changes via `bridge.py`, pushes updates to the browser via SSE (Stario `Relay`).

Communication is **implicit via shared SQLite file** — there is no HTTP, RPC, or socket connection between the two processes. The graph viewer polls the database and detects changes.

### Package Structure

**Remora library** (`src/remora/`):
- `core/` — EventStore, events, agent_node, subscriptions, swarm_executor, discovery, config
- `lsp/` — Server, runner, handlers, models, db, graph, watcher, notifications
- `service/` — RemoraService, chat_service, Datastar helpers
- `ui/` — UiStateProjector, component system (dashboard, layout, data, controls)
- `cli/` — Typer-based CLI (swarm start/reconcile/list/emit, serve)
- `extensions.py` — AgentExtension base class + file loader
- `testing/` — FakeAsyncOpenAI and test helpers

**remora_demo/** (in library repo):
- `neovim/mock_llm.py` — MockLLMClient importing from `remora.lsp.runner`
- `web/graph/` — Graph viewer (imports as `remora_demo.web.graph.*`)

**Frontend** (standalone repo):
- `graph/` — Graph viewer (imports as `graph.*`)
- `remora_demo/mock_llm.py` — MockLLMClient with standalone dataclasses
- `tests/` — 179 tests

### Key Architectural Decisions

1. **Event sourcing** — All agent activity is persisted as events in SQLite. Nodes table is a materialized projection.
2. **LSP as the backbone** — The editor connection IS the server. No separate backend process.
3. **Server-rendered SVG** — Graph viewer renders SVG server-side, streams to browser via SSE. No JavaScript framework.
4. **Tree-sitter for discovery** — Code nodes are discovered by parsing AST, not by regex or manual annotation.
5. **Extension model** — `.remora/models/` directory holds Python files that subclass `AgentExtension` to customize agent behavior.

---

## 3. Data Flow Analysis

### Event Lifecycle: Code Edit to Graph Render

```
1. User edits file in Neovim
       │
       ▼
2. LSP did_save handler (handlers/documents.py:~80)
       │
       ├─► ASTWatcher.scan_file() — tree-sitter parse
       │       Returns list[dict] of discovered nodes
       │
       ├─► EventStore.upsert_nodes() — update nodes table
       │       Emits NodeDiscoveredEvent for new/changed nodes
       │
       ├─► RemoraDB.update_edges() — update edges table
       │       Parent-child and caller-callee relationships
       │
       └─► server.notify_agents_updated() — LSP notification to Neovim
               Sends $/remora/agentsUpdated with all active nodes

3. Agent trigger (chat, subscription match, file save)
       │
       ▼
4. AgentRunner.trigger() — cascade checks (depth, cooldown, cycle)
       │
       ▼
5. AgentRunner.execute_turn()
       │
       ├─► EventStore.get_node(agent_id) — load AgentNode
       ├─► apply_extensions() — match .remora/models/*.py
       ├─► Build messages (system prompt + event history)
       ├─► LLMClient.chat() — call LLM with tools
       │
       ├─► Tool loop (up to 5 rounds):
       │   ├─ rewrite_self → create_proposal() → RemoraDB.store_proposal()
       │   ├─ message_node → emit AgentMessageEvent → trigger target agent
       │   └─ read_node   → EventStore.get_node() → return source code
       │
       └─► emit_event() → EventStore.append() + LSP $/remora/event notification

6. Graph viewer polling (bridge.py)
       │
       ├─► GraphState.snapshot() — read nodes + edges from SQLite
       │       Opens read-only connection to indexer.db
       │       Reads nodes table (EventStore schema)
       │       Reads edges table (RemoraDB schema)
       │
       ├─► ForceLayout.step() — compute node positions
       │
       ├─► SVG rendering (svg.py) — build SVG string
       │
       └─► Relay.send() → SSE → Browser update
```

### Key Data Paths

| Path | Source | Destination | Mechanism |
|------|--------|-------------|-----------|
| Code discovery | ASTWatcher | EventStore nodes table | `upsert_nodes()` via `asyncio.to_thread` |
| Edge updates | ASTWatcher | RemoraDB edges table | `update_edges()` via `async_db` decorator |
| Agent events | AgentRunner | EventStore events table | `emit_event()` → `EventStore.append()` |
| Proposals | AgentRunner | RemoraDB proposals table | `store_proposal()` via `async_db` |
| Graph reads | Graph viewer | Both tables | `GraphState.snapshot()` via read-only SQLite connection |
| UI updates | Graph viewer | Browser | Stario `Relay` → SSE stream |
| Commands | Web UI | LSP server | `RemoraDB.push_command()` → `poll_command_queue()` |

### Observation: Command Queue as IPC

The `command_queue` table in RemoraDB serves as a crude inter-process communication channel. The graph viewer's web UI can insert commands (e.g., "chat with agent X") by writing to this table (`push_command()` at `db.py:224`), which the LSP server's `AgentRunner.poll_command_queue()` polls every 1 second (`runner.py:296`). This is functional but has no delivery guarantees, no ordering beyond AUTOINCREMENT, and no backpressure mechanism.

---

## 4. Module-Level Singleton Issue

**Severity: CRITICAL**

### The Problem

`src/remora/lsp/server.py:148` creates a module-level singleton:

```python
# server.py:129-148
_server: RemoraLanguageServer | None = None

def get_server() -> RemoraLanguageServer:
    global _server
    if _server is None:
        _server = RemoraLanguageServer()  # event_store=None!
        atexit.register(_server.shutdown)
    return _server

# Line 148:
server = get_server()
```

This happens at **import time**. The constructor at `server.py:24-41` runs with `event_store=None`:

```python
def __init__(self, event_store=None, subscriptions=None, swarm_state=None):
    super().__init__(name="remora", version="0.1.0")
    self.db = RemoraDB()  # Creates .remora/indexer.db immediately
    self.event_store = event_store  # None!
    es_db_path = str(event_store._db_path) if event_store else None
    self.graph = LazyGraph(self.db, event_store_db_path=es_db_path)  # None path!
```

Then `__main__.py` must create an EventStore and overwrite the singleton's attributes **after** import:

```python
# __main__.py creates EventStore, then:
server.event_store = event_store
server.graph = LazyGraph(server.db, event_store_db_path=str(db_path))
```

### Why This Is Critical

1. **Ordering dependency** — Any module that imports `server` gets the `event_store=None` version. Handler decorators register on this instance at import time (line 170: `register_handlers()`). If any handler runs before `__main__.py` patches the server, `event_store` will be None.

2. **RemoraDB created too early** — `RemoraDB()` at line 31 creates `.remora/indexer.db` immediately in the constructor. This happens before the caller can specify a database path.

3. **LazyGraph initialized with None path** — `event_store_db_path=None` means the graph cannot read node data until re-initialized.

4. **atexit handler on the wrong instance** — If someone creates a second `RemoraLanguageServer` (e.g., in tests), the atexit handler only cleans up the first one.

### Recommended Fix

Replace the module-level singleton with a proper factory pattern:

```python
# Option A: Deferred initialization
class RemoraLanguageServer(LanguageServer):
    def initialize(self, event_store, subscriptions=None, swarm_state=None):
        """Called by __main__.py after construction."""
        self.event_store = event_store
        self.graph = LazyGraph(self.db, event_store_db_path=str(event_store._db_path))
        # ...
```

Or use a dependency injection container that handlers can reference without needing the instance at import time.

---

## 5. Dual Event Type Systems

**Severity: CRITICAL**

### Two Parallel Type Hierarchies

**System A: `core/events.py`** — Frozen dataclasses (the "real" events)
```python
@dataclass(frozen=True, slots=True)
class AgentMessageEvent:
    from_agent: str
    to_agent: str
    content: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    correlation_id: str | None = None
    timestamp: float = field(default_factory=time.time)

@dataclass(frozen=True, slots=True)
class AgentErrorEvent:
    graph_id: str
    agent_id: str
    error: str
    timestamp: float = field(default_factory=time.time)
```

**System B: `lsp/models.py`** — Pydantic BaseModel subclasses (the LSP events)
```python
class AgentMessageEvent(AgentEvent):  # Same name!
    from_agent: str = ""
    to_agent: str = ""
    message: str = ""  # Different field name: "message" vs "content"

class AgentErrorEvent(AgentEvent):  # Same name!
    error: str = ""
```

### Name Collisions

Both modules export `AgentMessageEvent` and `AgentErrorEvent` with the **same class names** but **different types and field names**. The LSP models module handles this internally with aliased imports:

```python
# lsp/models.py:10-15
from remora.core.events import (
    AgentCompleteEvent as CoreAgentCompleteEvent,
    AgentErrorEvent as CoreAgentErrorEvent,
    AgentMessageEvent as CoreAgentMessageEvent,
    ManualTriggerEvent as CoreManualTriggerEvent,
)
```

But `remora/__init__.py` re-exports **both** without aliases — the core versions from `core.events` AND `AgentRunner` which imports the Pydantic versions. Any consumer importing from the top-level package gets the core frozen dataclasses, but the runner internally uses the Pydantic versions.

### Conversion Overhead

Each Pydantic event class has a `to_core_event()` method (`models.py:108-243`), but **it is never called in the main code path**. Instead, `server.emit_event()` at `server.py:57-65` passes Pydantic models directly to `EventStore.append()`:

```python
async def emit_event(self, event) -> Any:
    if self.event_store:
        await self.event_store.append("swarm", event)  # Pydantic model, not core event!
    self.protocol.notify("$/remora/event", event.model_dump())
```

The EventStore's `append()` method then serializes using `asdict()` for dataclasses or `model_dump()` for Pydantic — it handles both, but this means the events table contains a mix of serialization formats.

### Field Name Divergence

| Concept | `core/events.py` field | `lsp/models.py` field |
|---------|----------------------|---------------------|
| Message content | `content` | `message` |
| Error text | `error` | `error` |
| Agent identity | `agent_id` (some have `from_agent`) | `agent_id` field on base `AgentEvent` |
| Graph identity | `graph_id` | `correlation_id` (repurposed) |

### Recommendation

Converge on a single event type system. The core frozen dataclasses are the better foundation (immutable, typed, no serialization magic). The Pydantic models should be thin serialization adapters for the LSP wire protocol, not a parallel domain model.

---

## 6. Three SQLite Databases

**Severity: HIGH**

### Database Inventory

All three databases use the **same file** (`.remora/indexer.db`) but are accessed through different connection objects with different locking strategies:

| Database | Class | Connection | Lock | WAL Mode |
|----------|-------|-----------|------|----------|
| EventStore | `EventStore` | `asyncio.to_thread(sqlite3.connect, ...)` | `asyncio.Lock()` | Not explicitly set |
| RemoraDB | `RemoraDB` | `sqlite3.connect(...)` (sync) | `threading.Lock()` | Explicitly WAL |
| SubscriptionRegistry | `SubscriptionRegistry` | `sqlite3.connect(...)` (sync) | None visible | Not explicitly set |

### Schema Distribution

**EventStore** owns (`core/event_store.py:71-129`):
- `events` — Event log (graph_id, event_type, payload, timestamp, routing fields)
- `nodes` — Materialized projection of discovered code nodes (23 columns)

**RemoraDB** owns (`lsp/db.py:52-98`):
- `edges` — Graph relationships (from_id, to_id, edge_type)
- `activation_chain` — Cascade tracking (correlation_id, agent_id, depth)
- `proposals` — Rewrite proposals (proposal_id, old/new source, diff, status)
- `cursor_focus` — Single-row table for current cursor position
- `command_queue` — IPC queue for web UI → LSP server commands

**SubscriptionRegistry** owns (`core/subscriptions.py`):
- `subscriptions` — Agent event subscriptions

### Connection Issues

1. **Same file, different connections** — `RemoraDB.__init__()` at `db.py:40-48` opens a connection with `check_same_thread=False` and sets WAL mode. `EventStore.initialize()` at `event_store.py:61-64` opens another connection with `check_same_thread=False` but does NOT set WAL mode. If EventStore opens first, the journal mode may default to DELETE, and RemoraDB's WAL pragma only applies to its own connection.

2. **Graph viewer opens a third connection** — `GraphState.snapshot()` opens a read-only connection for polling. This works with WAL mode but can cause `SQLITE_BUSY` errors under DELETE journal mode.

3. **No connection pooling** — Each class manages its own connection. The `push_command()` method at `db.py:224` does not use the `async_db` decorator (unlike other methods), meaning it runs synchronously without the threading lock when called from the graph viewer web server.

4. **Default path coupling** — `RemoraDB.__init__()` defaults to `.remora/indexer.db` (line 40). EventStore gets its path from the caller. If these don't match, the system silently uses two different database files.

### Recommendation

Ensure WAL mode is set by the **first** connection opener (ideally EventStore). Consider a shared connection factory or at minimum document the required initialization order. The graph viewer's read-only access should use `?mode=ro` in the SQLite URI.

---

## 7. Code Duplication Between Repos

**Severity: HIGH**

### Graph Viewer: Two Copies

The graph viewer code exists in **both** repositories:

| File | Remora repo path | Frontend repo path |
|------|-----------------|-------------------|
| app.py | `remora_demo/web/graph/app.py` | `graph/app.py` |
| bridge.py | `remora_demo/web/graph/bridge.py` | `graph/bridge.py` |
| state.py | `remora_demo/web/graph/state.py` | `graph/state.py` |
| layout.py | `remora_demo/web/graph/layout.py` | `graph/layout.py` |
| svg.py | `remora_demo/web/graph/svg.py` | `graph/svg.py` |
| css.py | `remora_demo/web/graph/css.py` | `graph/css.py` |
| views/*.py | `remora_demo/web/graph/views/` | `graph/views/` |

The code is nearly identical but with **different import paths**:

```python
# Remora repo version:
from remora_demo.web.graph.state import GraphState
from remora_demo.web.graph.layout import ForceLayout

# Frontend repo version:
from graph.state import GraphState
from graph.layout import ForceLayout
```

### MockLLM: Structural Divergence

The MockLLM implementations have a more significant difference:

**Remora repo** (`remora_demo/neovim/mock_llm.py`):
```python
from remora.lsp.runner import ToolCall, LLMResponse  # Imports from library
```

**Frontend repo** (`remora_demo/mock_llm.py`):
```python
@dataclass
class ToolCall:  # Defines its own compatible versions
    name: str
    arguments: dict[str, Any]
    id: str = ""

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
```

The frontend version defines its own `ToolCall` and `LLMResponse` dataclasses that are structurally compatible with the library versions but are separate types. This is intentional — the frontend repo must work without installing the full Remora library.

### Drift Risk

With no automated sync mechanism:
- Bug fixes in one copy won't appear in the other
- New features added to the remora_demo version won't be reflected in frontend
- The import path difference prevents simple copy-paste

### Recommendation

Choose one canonical location. If the frontend repo is the "development" copy (where tests live), consider making remora_demo import from it, or use a git submodule / shared package.

---

## 8. Two Runner Paths

**Severity: HIGH**

### AgentRunner vs SwarmExecutor

The system has two distinct execution engines:

**AgentRunner** (`lsp/runner.py:167-835`):
- Used by the LSP server
- Manages its own trigger queue, cascade prevention, tool loop
- Calls LLMClient directly
- Has `create_headless()` for CLI mode

**SwarmExecutor** (`core/swarm_executor.py`, 400 lines):
- Used by the CLI `swarm start` command
- Manages its own SwarmState, agent metadata
- Has its own run loop and event processing
- Independent cascade tracking

### Dead Executor Branch

In `AgentRunner.execute_turn()` at `runner.py:422-426`:

```python
if self.executor:
    state = await self._load_agent_state(agent_id)
    if state:
        trigger_event = await self._build_trigger_event(trigger)
        await self.executor.run_agent(state, trigger_event)
```

But `_load_agent_state()` at `runner.py:507-508`:

```python
async def _load_agent_state(self, agent_id: str) -> Any:
    return None  # Always returns None!
```

This means the `if self.executor:` branch is **dead code**. Even if `self.executor` is set, `_load_agent_state` always returns `None`, so `self.executor.run_agent()` is never called.

The `executor` attribute is declared at `runner.py:186`:
```python
self.executor: "SwarmExecutor | None" = None
```

Nothing in the codebase ever sets it to a non-None value.

### Implications

1. The SwarmExecutor exists as a separate, independent system that cannot be reached through AgentRunner.
2. The AgentRunner's `create_headless()` class method creates a fully functional headless runner without SwarmExecutor.
3. The SwarmExecutor has its own copy of cascade prevention logic, its own event processing, its own agent state management.

### Recommendation

Either complete the SwarmExecutor integration (implement `_load_agent_state`, wire `executor` in construction) or remove the dead branch and unify both paths through AgentRunner. The `create_headless()` pattern already proves AgentRunner can work without the LSP server.

---

## 9. Thread Safety & Concurrency

**Severity: HIGH**

### Lock Inventory

| Component | Lock Type | Scope | Protects |
|-----------|----------|-------|----------|
| EventStore | `asyncio.Lock()` | Per-instance | All DB operations |
| RemoraDB | `threading.Lock()` | Per-instance | Methods decorated with `@async_db` |
| GraphState | None | Per-call | Opens new read-only connection each time |
| SubscriptionRegistry | None visible | Per-instance | SQLite operations |

### Mixed Lock Types

EventStore uses `asyncio.Lock()` — this only works within a single event loop. If EventStore methods are called from a different thread (which `asyncio.to_thread` creates), the asyncio lock does NOT protect against cross-thread access. However, the EventStore wraps all SQLite calls in `asyncio.to_thread()`, and the `asyncio.Lock()` ensures only one coroutine enters the critical section at a time within the event loop, so the thread safety comes from serialization rather than the lock itself.

RemoraDB uses `threading.Lock()` — this properly protects against multi-thread access. The `@async_db` decorator at `db.py:18-29` wraps each method call in `asyncio.to_thread` with the lock held.

### Unlocked Methods

`RemoraDB.push_command()` at `db.py:224-235` is **NOT** decorated with `@async_db`:

```python
def push_command(self, command_type: str, agent_id: str | None, payload: dict) -> int:
    cursor = self.conn.cursor()  # No lock!
    cursor.execute(...)
    self.conn.commit()
    return cursor.lastrowid
```

This method is called from the graph viewer web server (a different process, so the threading lock wouldn't help anyway), but also potentially from within the LSP server process. If called concurrently with other RemoraDB methods, it could corrupt state.

Similarly, `RemoraDB.get_cursor_focus()` at `db.py:115-120` and `RemoraDB.poll_commands()` at `db.py:237-244` are not decorated with `@async_db`, meaning they run without the threading lock.

### asyncio.Semaphore in AgentRunner

The runner uses `asyncio.Semaphore(4)` at `runner.py:197` to limit concurrent agent executions:

```python
async with self._semaphore:
    await self.server.event_store.set_node_status(agent_id, "running")
    ...
```

This is well-designed — it prevents overloading the LLM with too many simultaneous requests.

### Graph Viewer Concurrency

The graph viewer (`bridge.py`) opens a new SQLite connection for each poll cycle. Since it runs in a separate process, this is safe. However, without WAL mode, concurrent reads from the graph viewer and writes from the LSP server could cause `SQLITE_BUSY` errors with the default journal mode.

### Recommendation

1. Ensure WAL mode is set consistently across all connections.
2. Add `@async_db` to `push_command()`, `get_cursor_focus()`, and `poll_commands()`.
3. Document the threading model: "EventStore serializes via asyncio.Lock, RemoraDB serializes via threading.Lock, cross-process access relies on WAL mode."

---

## 10. Error Handling Patterns

**Severity: MEDIUM**

### Broad Exception Swallowing in LSP Handlers

Most LSP handlers wrap their entire body in `try/except Exception`:

**`handlers/documents.py` — did_open:**
```python
@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
async def did_open(params):
    try:
        # ... entire handler body (~70 lines) ...
    except Exception:
        logger.exception("did_open: FAILED for %s", params.text_document.uri)
```

**`handlers/commands.py` — cmd_get_agent_panel:**
```python
@server.command("remora.getAgentPanel")
async def cmd_get_agent_panel(ls, *args):
    try:
        # ... entire handler body ...
    except Exception:
        logger.exception("cmd_get_agent_panel: FAILED")
        return None
```

This is a defensive pattern common in LSP servers (crashing the server kills the editor integration), but it has consequences:

1. **Silent failures** — If `event_store` is None (see Section 4), methods like `list_nodes()` will raise `AttributeError`, which gets logged but never surfaces to the user.
2. **Return value ambiguity** — When an exception is caught, handlers return `None` or nothing. The LSP client cannot distinguish "no agent at this position" from "server error."
3. **No error categorization** — All exceptions are treated identically. A `FileNotFoundError` from tree-sitter and a `sqlite3.OperationalError` from a locked database get the same treatment.

### Positive Patterns

The `AgentRunner` has better error handling:
- Cascade limit violations emit `AgentErrorEvent` to the UI (`runner.py:372,380,385`)
- The concurrency semaphore ensures agent executions can't deadlock (`runner.py:408`)
- Tool call errors are caught per-tool and reported individually

### server.py: Silent Swallowing

```python
# server.py:47-51
async def refresh_code_lenses(self) -> None:
    try:
        await self.workspace_code_lens_refresh_async()
    except Exception:
        pass  # Completely silent!
```

This suppresses errors from code lens refresh entirely — no logging, no tracking.

### Recommendation

1. Add structured error responses for LSP commands (return `{"error": "..."}` instead of `None`).
2. Log at WARNING level for expected failures, ERROR for unexpected.
3. Replace bare `except Exception: pass` with at minimum `logger.debug()`.
4. Consider an error boundary decorator that categorizes exceptions.

---

## 11. Service Layer Analysis

**Severity: MEDIUM (mostly unused in demo path)**

### RemoraService (`service/api.py`)

`RemoraService` is a framework-agnostic facade for the Remora system. It is used by the `remora serve` CLI command to expose a web dashboard.

Key observations:

1. **Separate database paths** — `RemoraService.create_default()` at `api.py:54` uses `.remora/events/events.db` for EventStore, `.remora/subscriptions.db` for subscriptions, and `.remora/swarm_state.db` for swarm state. This is a **different path** from the LSP server's `.remora/indexer.db`. The service layer and LSP layer use different databases.

2. **UiStateProjector** — Listens to EventBus events and builds a dashboard state. This is a well-designed projection pattern.

3. **Datastar integration** — `service/datastar.py` provides SSE rendering helpers for the Datastar frontend framework. This is a different rendering approach from the graph viewer's Stario/SVG approach.

### ChatService (`service/chat_service.py`)

A standalone Starlette application for LLM chat sessions. Uses `sse_starlette` for streaming. Has its own module-level state singleton (`state = ChatServiceState()` at line 46).

This is completely independent of the LSP server — it's a separate web service that can be deployed standalone.

### Observation

The service layer (`service/`) is designed for a web dashboard use case that is **orthogonal** to the demo's graph viewer. The demo's graph viewer (Stario) reads directly from the LSP server's SQLite database. The service layer would be used for a standalone "remora serve" deployment. These two UI paths share no code.

---

## 12. UI Component System

**Severity: LOW**

### Component Hierarchy (`ui/components/`)

The library includes a Python-based HTML component system:

```
Component (ABC)                    # base.py:10
├── ComponentGroup                 # base.py:25 — sequential rendering
├── Element                        # base.py:50+ — generic HTML element
├── RawHTML                        # base.py:~100 — raw HTML string passthrough
├── Card, Container, Grid          # layout.py — layout primitives
├── Button, Input, Select          # controls.py — form elements
├── List, ProgressBar, StatusBadge # data.py — data display
└── EventsList, GraphLauncher, ... # dashboard.py — dashboard-specific
```

All components render to HTML strings via `.render()`. This is used by the `remora serve` web dashboard via Datastar SSE patches.

### Not Used by the Demo

The graph viewer in the frontend repo does **not** use this component system. It builds SVG directly via f-string builders (`svg.py`) and wraps in Stario's `SafeString`. The component system is only relevant for the `remora serve` dashboard path.

### Design Quality

The component system is clean and well-structured:
- `Component` is abstract with a clear `render() -> str` contract
- `Element` handles attribute serialization and HTML escaping
- Layout components compose via children
- Dashboard components have domain-specific rendering logic

No issues identified. The main concern is that it's parallel infrastructure to the graph viewer's approach.

---

## 13. Testing Coverage Analysis

**Severity: MEDIUM**

### Frontend Repo: Strong Coverage

**179 tests, all passing.** Organized as:

| Test file | Count | Covers |
|-----------|-------|--------|
| `test_layout.py` | ~30 | ForceLayout: spring forces, damping, convergence |
| `test_svg.py` | ~25 | SVG element builders: nodes, edges, markers |
| `test_css.py` | ~15 | CSS theme rendering, custom properties |
| `test_state.py` | ~20 | GraphState: SQLite reads, node/edge parsing |
| `test_bridge.py` | ~15 | DB→Relay bridge: polling, change detection |
| `test_app.py` | ~15 | Stario app structure, routes, handlers |
| `test_views.py` | ~12 | View functions: shell, graph, sidebar |
| `test_mock_llm.py` | 19 | MockLLMClient: scripted responses, tool calls |
| `test_entry_points.py` | 10 | LSP entry point structure, launch.sh |
| `test_golden_path.py` | 18 | End-to-end: discovery → agent trigger → proposal → graph |

**Strengths:**
- Pure function testing for SVG, CSS, layout — no mocking needed
- GraphState tests use real in-memory SQLite databases
- Golden path tests verify the full event flow without external dependencies
- MockLLM tests cover multi-turn conversations with tool calls

**Gaps:**
- No tests for actual Stario HTTP handler behavior (SSE streaming)
- No tests for concurrent bridge polling
- No integration tests against the real Remora library

### Remora Library: Extensive but Untested Integration Points

The library has 80+ test files covering core functionality:
- EventStore, agent_node, events, subscriptions, projections
- Discovery (tree-sitter parsing)
- SwarmExecutor, reconciler
- Config, workspace, tools

**Gaps in the library:**
- No tests for `lsp/server.py` singleton initialization sequence
- No tests for the runner's tool loop with real LLM responses
- No tests for cross-database consistency (EventStore + RemoraDB)
- No integration tests between the LSP server and graph viewer

### Cross-Repo Gap

**Zero tests verify that the frontend and library work together.** The frontend's test suite uses mock/fake data that matches the expected schema, but if the library's schema changes (e.g., a new column in the nodes table), the frontend tests would still pass while the actual integration would break.

---

## 14. Import & Dependency Issues

**Severity: MEDIUM**

### ConfigError Shadow Import

`src/remora/__init__.py:5-8` imports `ConfigError` from `remora.core.config`:
```python
from remora.core.config import (
    Config,
    ConfigError,  # First import
    load_config,
    serialize_config,
)
```

Then at lines 18-19, it imports `ConfigError` again from `remora.core.errors`:
```python
from remora.core.errors import (
    ConfigError,  # Shadows the first import!
    DiscoveryError,
    ...
)
```

Both modules define `ConfigError`, but `core/config.py` likely re-exports from `core/errors.py`, so they may be the same class. If they're different classes (e.g., if `config.py` defines its own), the second import silently shadows the first.

### Heavyweight Dependency List

The Remora library's `pyproject.toml` lists **30+ dependencies** including:
- `structured-agents>=0.3.4` (git source)
- `grail>=3.0.0` (git source)
- `cairn` (git source)
- `fsdantic>=0.2.0` (git source)
- `fastapi>=0.133.1`
- `starlette>=0.30`
- `uvicorn>=0.23`
- `tree-sitter>=0.20` + language grammars
- `openai>=1.0`
- `pygls` + `lsprotocol`
- `rustworkx>=0.17.1`
- `pydantic>=2.0`

Four dependencies are **git-sourced** (`fsdantic`, `cairn`, `structured-agents`, `grail`), meaning builds require network access to specific GitHub repositories and are pinned to branches, not versions. This creates reproducibility risk.

### Python Version Split

- **Remora library**: `requires-python = ">=3.13"`
- **Frontend**: `requires-python = ">=3.14"`

This is by design (Stario requires 3.14), but it means the two cannot be installed in the same virtual environment. The frontend's `pyproject.toml` lists `stario` and `httpx` as its only runtime dependencies — a much lighter footprint.

### Build System Difference

- Remora: `hatchling>=1.18`
- Frontend: `setuptools>=68`

Not a problem, but notable for consistency.

---

## 15. Dead Code & Unused Exports

**Severity: LOW**

### Dead Code

1. **`AgentRunner.executor` branch** (covered in Section 8) — `_load_agent_state()` always returns `None`.

2. **`AgentRunner._build_trigger_event()`** at `runner.py:510-518` — Only called from the dead executor branch. Never actually executed.

3. **`_HeadlessDB` methods** at `runner.py:132-148` — All methods are stubs that return empty values. `_HeadlessDB.poll_commands()` returns `[]`, `mark_command_done()` is a no-op. These exist for duck-type compatibility with `RemoraDB` in headless mode.

4. **Commented-out pyproject.toml sections**:
   - `remora/pyproject.toml:60-63`: Commented-out `[project.optional-dependencies] all` section
   - `remora/pyproject.toml:78-80`: Commented-out `[project.urls]` section
   - `remora/pyproject.toml:42-43`: Commented-out `stario` dependency in frontend extras

### Unused Public Exports

`remora/__init__.py` exports 40+ symbols. Several are unlikely to be used by external consumers:
- `CairnWorkspaceService`, `CairnExternals`, `CairnDataProvider` — Cairn is a specific workspace framework
- `get_agent_dir`, `get_agent_state_path`, `get_agent_workspace_path` — Internal path helpers
- `build_virtual_fs` — Grail-specific utility

### Vestigial Features

The `RemoraGrailTool` (`core/tools/grail.py`) is tightly coupled to the Grail execution environment. If Grail is not used, this code is dead weight. Similarly, `CairnWorkspaceService` and `CairnExternals` are only relevant if using the Cairn workspace system.

---

## 16. Integration Risk Assessment

**Severity: HIGH**

### End-to-End Failure Modes

| Failure | Cause | Effect | Detection |
|---------|-------|--------|-----------|
| **Singleton not initialized** | Import `server` before `__main__.py` patches it | `event_store` is None, all handlers fail silently | Only visible in logs |
| **Database path mismatch** | EventStore uses caller-provided path, RemoraDB defaults to `.remora/indexer.db` | Graph viewer reads from wrong DB; nodes and edges in different files | Silent — data just doesn't appear |
| **WAL mode not set** | EventStore opens before RemoraDB sets WAL | Graph viewer gets SQLITE_BUSY errors during writes | Intermittent read failures |
| **Schema drift** | Library adds column to nodes table | Graph viewer's `GraphState` queries break | Runtime error on first poll |
| **Mock/Real LLM mismatch** | MockLLM returns hardcoded tool calls; real LLM returns different format | Runner's tool dispatch fails | Only caught in real integration |
| **Import path divergence** | Frontend uses `graph.*`, remora_demo uses `remora_demo.web.graph.*` | Same code, different packages; can't share test infrastructure | Manual comparison only |

### Most Likely Integration Breakage

1. **Database initialization order** — If the `__main__.py` entry point changes the order in which EventStore and RemoraDB are created, or changes the database path, the graph viewer silently stops receiving data.

2. **Event type confusion** — A handler emitting a Pydantic `AgentErrorEvent` (from `lsp/models.py`) instead of the core frozen `AgentErrorEvent` (from `core/events.py`) will serialize differently in the events table. Code that reads events and pattern-matches on type will get unexpected results.

3. **MockLLM drift** — The frontend repo's MockLLMClient defines its own `ToolCall` and `LLMResponse`. If the library changes the `ToolCall` fields (e.g., adding a `type` field), the mock won't match and integration tests will pass while real integration fails.

### Risk Mitigation

The frontend repo's golden path tests (`test_golden_path.py`) are the primary defense against integration breakage. They test the full flow from discovery to graph rendering using mock data that mirrors the library's schema. However, they cannot detect library-side schema changes.

**Recommendation:** Add a CI step that installs both the library and frontend, creates a shared database, and verifies the graph viewer can read nodes written by the library's EventStore.

---

## 17. Recommendations

### Critical Priority

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| C1 | Module-level singleton (`server.py:148`) | Replace with factory + deferred initialization pattern. Remove `server = get_server()` at module level. | 2-4 hours |
| C2 | Dual event type systems | Converge on core frozen dataclasses as the canonical event types. Make Pydantic models thin serialization adapters for the LSP wire protocol only. | 4-8 hours |

### High Priority

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| H1 | Three SQLite databases, inconsistent WAL | Ensure WAL mode is set by the first opener. Add `PRAGMA journal_mode=WAL` to EventStore initialization. | 30 min |
| H2 | Code duplication across repos | Choose one canonical location for graph viewer. Use git submodule or shared package with configurable import paths. | 2-4 hours |
| H3 | Dead executor branch in runner | Remove `if self.executor:` branch and `_load_agent_state()` / `_build_trigger_event()`. Or implement the integration. | 1-2 hours |
| H4 | Thread safety gaps in RemoraDB | Add `@async_db` decorator to `push_command()`, `get_cursor_focus()`, `poll_commands()`. | 30 min |

### Medium Priority

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| M1 | Broad exception swallowing | Add structured error returns for LSP commands. Replace `except Exception: pass` with logging. | 2-4 hours |
| M2 | ConfigError shadow import | Verify both imports resolve to the same class. If so, remove the duplicate. If not, fix the shadowing. | 15 min |
| M3 | No cross-repo integration tests | Add CI job that creates shared database and tests library → graph viewer data flow. | 4-8 hours |
| M4 | Heavyweight git-sourced dependencies | Pin to specific commits rather than branches. Consider publishing to a private PyPI. | 2-4 hours |
| M5 | Command queue as IPC | Document limitations. Add delivery timeout (clean up commands older than N seconds). | 1-2 hours |

### Low Priority

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| L1 | Commented-out pyproject.toml sections | Clean up or remove with explanatory comments. | 15 min |
| L2 | Unused public exports in `__init__.py` | Audit `__all__` and reduce to actually-used symbols. | 30 min |
| L3 | Parallel UI systems (component system vs SVG builders) | Document when to use which. No code change needed. | 30 min |

### Implementation Order

For the demo to work reliably end-to-end:

1. **H1** (WAL mode) — Fastest fix, prevents the most common runtime error
2. **C1** (singleton) — Blocks reliable initialization
3. **H4** (thread safety) — Prevents rare but catastrophic data corruption
4. **C2** (event types) — Prevents data format confusion
5. **H3** (dead code) — Reduces confusion for maintainers
6. **M3** (integration tests) — Prevents future regressions
7. **H2** (code duplication) — Prevents drift

---

*End of review.*
