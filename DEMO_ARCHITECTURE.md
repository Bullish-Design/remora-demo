# DEMO_ARCHITECTURE.md — Remora System Architecture

> Comprehensive architectural reference for the Remora agent system, covering the core engine, the Neovim demo (LSP integration), and the Web demo (Stario + Datastar frontend). Particular attention is paid to **crossover interfaces** — the boundaries where data moves between systems, the shape of that data, and the constraints to be aware of.

---

## Table of Contents

1. [System Overview](#1-system-overview) — High-level diagram of the three major subsystems (Core, Neovim/LSP, Web/Service) and how they connect.

2. [Remora Core Architecture](#2-remora-core-architecture) — The engine that powers everything: events, discovery, agent model, subscriptions, projections, workspace, and execution.
   - 2.1 [Event System](#21-event-system) — Event types, EventBus, EventStore, and event sourcing with SQLite.
   - 2.2 [Discovery Pipeline](#22-discovery-pipeline) — Tree-sitter based code parsing, CSTNode, node ID computation, `.scm` query files.
   - 2.3 [Agent Model (AgentNode)](#23-agent-model-agentnode) — The Pydantic BaseModel that serves triple duty: DB row, LLM prompt, and LSP protocol response.
   - 2.4 [Subscriptions & Reactive Routing](#24-subscriptions--reactive-routing) — SubscriptionPattern, SubscriptionRegistry, how events trigger agent runs.
   - 2.5 [Projections](#25-projections) — NodeProjection: how the event log materializes into the `nodes` table.
   - 2.6 [Workspace & Cairn Integration](#26-workspace--cairn-integration) — AgentWorkspace, CairnBridge, CairnExternals, copy-on-write isolation.
   - 2.7 [Executor (SwarmExecutor)](#27-executor-swarmexecutor) — How a single agent turn runs: bundle resolution, workspace init, externals, prompt building, kernel execution.
   - 2.8 [Extensions](#28-extensions) — AgentExtension base class, `.remora/models/` loading, first-match-wins priority.
   - 2.9 [Configuration](#29-configuration) — Config dataclass, `remora.yaml`, all field groups.
   - 2.10 [Error Hierarchy](#210-error-hierarchy) — RemoraError and its subclasses.

3. [The Data Flow Pipeline](#3-the-data-flow-pipeline) — End-to-end trace of how source code becomes agent activity.
   - 3.1 [Source Code to CSTNode](#31-source-code-to-cstnode) — File parsing, tree-sitter queries, node ID hashing.
   - 3.2 [CSTNode to EventStore](#32-cstnode-to-eventstore) — NodeDiscoveredEvent emission, JSON serialization, SQLite insertion.
   - 3.3 [EventStore to AgentNode](#33-eventstore-to-agentnode) — NodeProjection UPSERT, `nodes` table, `AgentNode.from_row()`.
   - 3.4 [Event to Trigger](#34-event-to-trigger) — SubscriptionRegistry matching, trigger queue, cascade prevention.
   - 3.5 [Trigger to Agent Turn](#35-trigger-to-agent-turn) — SwarmExecutor or AgentRunner consuming the trigger, running the LLM.

4. [Neovim Demo Architecture](#4-neovim-demo-architecture) — The LSP server that integrates Remora into Neovim as a language server.
   - 4.1 [LSP Server Structure](#41-lsp-server-structure) — RemoraLanguageServer, global singleton, handler registration.
   - 4.2 [AgentRunner](#42-agentrunner) — The unified async execution coordinator: trigger queue, cascade prevention, execute_turn, tool call loop.
   - 4.3 [RemoraDB (indexer.db)](#43-remoradb-indexerdb) — LSP-specific SQLite: edges, proposals, cursor_focus, command_queue, activation_chain.
   - 4.4 [LazyGraph](#44-lazygraph) — Graph topology backed by rustworkx, lazy neighborhood loading via recursive CTE.
   - 4.5 [ASTWatcher](#45-astwatcher) — File parsing, ID injection (`# rm_xxxx`), Python-specific tree-sitter handling.
   - 4.6 [Proposals & Rewrites](#46-proposals--rewrites) — RewriteProposal model, diagnostics, code actions, workspace edits.
   - 4.7 [LSP Handlers](#47-lsp-handlers) — Document lifecycle, hover, commands, code actions, code lens.
   - 4.8 [Custom Notifications](#48-custom-notifications) — `$/remora/cursorMoved`, `$/remora/submitInput`, `$/remora/event`, `$/remora/agentsUpdated`.
   - 4.9 [Agent Tools in Neovim Context](#49-agent-tools-in-neovim-context) — `rewrite_self`, `message_node`, `read_node`.

5. [Web Demo Architecture](#5-web-demo-architecture) — The Stario + Datastar web frontend and its service layer.
   - 5.1 [Service Layer (RemoraService)](#51-service-layer-remoraservice) — Framework-agnostic API, handler functions, event streaming.
   - 5.2 [Starlette Adapter](#52-starlette-adapter) — Route mapping, DatastarResponse, SSE streaming.
   - 5.3 [Datastar Integration](#53-datastar-integration) — `render_shell()`, `render_patch()`, `render_signals()`, SSE patch model.
   - 5.4 [UI Layer](#54-ui-layer) — UiStateProjector (event reduction), Component system, render_dashboard.
   - 5.5 [ChatService](#55-chatservice) — Standalone Starlette chat app, session management, SSE event streaming.
   - 5.6 [Graph Viewer (remora-demo frontend)](#56-graph-viewer-remora-demo-frontend) — Stario app, GraphState, DBBridge, force-directed layout, SVG rendering.

6. [Crossover Interfaces](#6-crossover-interfaces) — The main focus. Every boundary where data moves between subsystems.
   - 6.1 [Event Serialization Boundary](#61-event-serialization-boundary) — Event dataclass to JSON to SQLite and back.
   - 6.2 [EventStore to EventBus](#62-eventstore-to-eventbus) — In-process notification after persistence.
   - 6.3 [EventStore to SubscriptionRegistry to Trigger Queue](#63-eventstore-to-subscriptionregistry-to-trigger-queue) — Reactive routing within a single transaction.
   - 6.4 [AgentNode Triple Interface](#64-agentnode-triple-interface) — `to_row()`/`from_row()` (SQLite), `to_system_prompt()` (LLM), `to_code_lens()`/`to_hover()` (LSP).
   - 6.5 [SQLite as Shared State Bus](#65-sqlite-as-shared-state-bus) — How multiple processes share state through SQLite WAL mode.
   - 6.6 [command_queue Table](#66-command_queue-table) — Web frontend pushes commands, AgentRunner polls and dispatches.
   - 6.7 [cursor_focus Table](#67-cursor_focus-table) — Neovim cursor position to web graph highlight.
   - 6.8 [HTTP/SSE API Boundary](#68-httpsse-api-boundary) — Data shapes for all REST endpoints and SSE streams.
   - 6.9 [DBBridge Polling Loop](#69-dbbridge-polling-loop) — SQLite fingerprint polling, Relay publish, SSE to browser.
   - 6.10 [Cairn Externals Interface](#610-cairn-externals-interface) — How agent tools call through to the filesystem.
   - 6.11 [LSP Custom Notifications](#611-lsp-custom-notifications) — Data shapes for `$/remora/*` notifications between Neovim and the LSP server.
   - 6.12 [RemoraDB vs EventStore](#612-remoradb-vs-eventstore) — What lives where and why the separation exists.

7. [Shared State & SQLite Databases](#7-shared-state--sqlite-databases) — Catalog of every SQLite database, their tables, schemas, and access patterns.
   - 7.1 [events.db (EventStore)](#71-eventsdb-eventstore) — `events` table, `nodes` table, schema, indexes.
   - 7.2 [subscriptions.db (SubscriptionRegistry)](#72-subscriptionsdb-subscriptionregistry) — Subscription patterns, in-memory cache.
   - 7.3 [indexer.db (RemoraDB)](#73-indexerdb-remoradb) — Edges, proposals, cursor_focus, command_queue, activation_chain.
   - 7.4 [agents.db (SwarmState)](#74-agentsdb-swarmstate) — Swarm-level agent metadata registry.
   - 7.5 [workspace.db / stable.db (Cairn)](#75-workspacedb--stabledb-cairn) — Cairn workspace databases, CoW isolation.

8. [Startup & Lifecycle](#8-startup--lifecycle) — How the system boots in each mode and what happens at each stage.
   - 8.1 [CLI Headless Mode](#81-cli-headless-mode) — `remora swarm start`: config load, reconciliation, AgentRunner.create_headless, run_forever.
   - 8.2 [LSP Mode](#82-lsp-mode) — `remora swarm start --lsp`: reconciliation, then LSP server with background scan and runner.
   - 8.3 [Web Service Mode](#83-web-service-mode) — `remora serve`: RemoraService.create_default, Starlette app, uvicorn.
   - 8.4 [Graph Viewer Startup](#84-graph-viewer-startup) — Stario app factory, DBBridge initialization, route registration.

---

## 1. System Overview

Remora is an **event-sourced, reactive agent system** that treats every function, class, and file in a codebase as an autonomous agent. Three major subsystems exist:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          REMORA CORE                                    │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Discovery │  │  Events  │  │ Subscriptions│  │  SwarmExecutor    │  │
│  │ Pipeline  │  │ EventBus │  │  Registry    │  │  (agent turns)    │  │
│  │ (tree-    │  │ EventStore│  │             │  │                   │  │
│  │  sitter)  │  │ (SQLite) │  │  (SQLite)   │  │  Cairn Workspace  │  │
│  └──────────┘  └──────────┘  └──────────────┘  └───────────────────┘  │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ AgentNode│  │Projections│  │  Extensions  │  │    Config         │  │
│  │ (model)  │  │ (nodes   │  │  (.remora/   │  │  (remora.yaml)    │  │
│  │          │  │  table)  │  │   models/)   │  │                   │  │
│  └──────────┘  └──────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
        │                    │                              │
        │ SQLite WAL         │ SQLite WAL                   │ In-process
        │ (shared state)     │ (events.db)                  │ (event bus)
        ▼                    ▼                              ▼
┌──────────────────────┐  ┌────────────────────────────────────────────┐
│   NEOVIM DEMO (LSP)  │  │             WEB DEMO                      │
│                       │  │                                            │
│  RemoraLanguageServer │  │  ┌──────────────┐  ┌───────────────────┐  │
│  AgentRunner          │  │  │RemoraService  │  │  Graph Viewer     │  │
│  RemoraDB (indexer.db)│  │  │(Starlette)    │  │  (Stario app)     │  │
│  LazyGraph (rustworkx)│  │  │               │  │                   │  │
│  ASTWatcher           │  │  │ UiStateProj.  │  │  GraphState       │  │
│  Proposals            │  │  │ Datastar SSE  │  │  DBBridge→Relay   │  │
│                       │  │  │ ChatService   │  │  SVG + Layout     │  │
│  ◄──► Neovim client   │  │  └──────────────┘  └───────────────────┘  │
│       (custom notifs) │  │        ▲ SSE              ▲ SSE           │
└──────────────────────┘  │        │                   │               │
        │                  │        ▼                   ▼               │
        │                  │     Browser (Datastar)  Browser (Datastar)│
        │ cursor_focus     └────────────────────────────────────────────┘
        │ command_queue
        └──────────────►  indexer.db  ◄──────────────┘
                          (shared via SQLite WAL)
```

**Key architectural principle**: SQLite databases in WAL mode serve as the **inter-process communication bus**. The Neovim LSP server, the web service, and the graph viewer all read from the same `events.db` and `indexer.db` files. There is no message broker, no Redis, no network protocol between them — just filesystem-level database sharing.

**Three modes of operation**:
- **CLI Headless** (`remora swarm start`): Core + AgentRunner, no UI. Reconciles, runs agents in a loop.
- **LSP Mode** (`remora swarm start --lsp`): Core + LSP server inside Neovim. AgentRunner runs as a background task within the LSP process.
- **Web Service** (`remora serve`): Core + Starlette HTTP server with Datastar SSE streaming. Separate process from LSP.

The **Graph Viewer** (this repo's `frontend/`) is a standalone Stario web app that connects to `events.db` read-only via `GraphState` and `DBBridge`.

---

## 2. Remora Core Architecture

Source: `remora/src/remora/core/`

The core is a pure-Python library with no framework dependencies. It provides event sourcing, code discovery, an agent model, reactive subscriptions, workspace management, and an execution engine. Everything above it (LSP, web service, graph viewer) is a consumer of core APIs.

### 2.1 Event System

The event system has three layers: event types (data), EventBus (in-process routing), and EventStore (persistence + reactive triggers).

#### Event Types (`core/events.py`, 227 lines)

All events are **frozen dataclasses** with `slots=True`. They fall into categories:

| Category | Events | Purpose |
|----------|--------|---------|
| Agent lifecycle | `AgentStartEvent`, `AgentCompleteEvent`, `AgentErrorEvent` | Track when agents begin, finish, or fail |
| Human-in-the-loop | `HumanInputRequestEvent`, `HumanInputResponseEvent` | Agent asks user a question, user responds |
| Reactive swarm | `AgentMessageEvent`, `FileSavedEvent`, `ContentChangedEvent`, `ManualTriggerEvent` | Inter-agent communication, file changes, manual triggers |
| Node lifecycle | `NodeDiscoveredEvent`, `NodeRemovedEvent` | Code nodes found or deleted during discovery |
| Kernel (re-exported) | `KernelStartEvent`, `KernelEndEvent`, `ToolCallEvent`, `ToolResultEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `TurnCompleteEvent` | From `structured_agents` — LLM interaction events |

The union type `RemoraEvent` covers all of these.

Key fields shared by most events: `agent_id: str`, `graph_id: str`, `timestamp: float`. Some events (like `AgentMessageEvent`) add `from_agent`, `to_agent`, `content`, `tags`.

#### EventBus (`core/event_bus.py`, 139 lines)

The in-process pub/sub system. Implements the `structured_agents.Observer` protocol via its `emit()` method.

```python
# API
bus.emit(event)                              # Fire-and-forget to all subscribers
bus.subscribe(EventType, handler)            # Subscribe to specific type
bus.subscribe_all(handler)                   # Subscribe to everything
async with bus.stream(EventType) as events:  # Async iterator via asyncio.Queue
    async for event in events: ...
await bus.wait_for(EventType, predicate, timeout)  # One-shot with predicate
```

Error policy: `"log"` (default, swallows handler exceptions) or `"propagate"` (re-raises).

**Important**: EventBus is purely in-memory. It does not persist anything. It's the notification layer that fires *after* EventStore has persisted an event.

#### EventStore (`core/event_store.py`, 603 lines)

The **central persistence and reactive trigger engine**. SQLite-backed with two tables:

- **`events`**: append-only event log. Columns: `id`, `graph_id`, `event_type`, `event_data` (JSON), `timestamp`, `agent_id`.
- **`nodes`**: materialized view of current node state (maintained by NodeProjection).

The `append(graph_id, event)` method is the most critical function in the system. It:
1. Serializes the event to JSON
2. INSERTs into the `events` table
3. Runs `NodeProjection.apply()` **in the same transaction** (updates `nodes` table)
4. Checks `SubscriptionRegistry` for matching agents
5. Queues matching agents into the trigger queue
6. Emits to EventBus (in-process notification)

All DB operations use `asyncio.to_thread` with an `asyncio.Lock` for serialization.

Other key methods: `replay(graph_id)`, `get_recent_events(graph_id, limit)`, node CRUD (`list_nodes()`, `get_node()`, `upsert_node()`, `delete_node()`).

### 2.2 Discovery Pipeline

Source: `core/discovery.py` (340 lines)

Discovers code structure using **tree-sitter** parsers. Supports: Python, JavaScript, TypeScript, Go, Rust, Markdown, TOML, YAML, JSON.

**CSTNode** — a frozen dataclass representing a discovered code element:
```python
@dataclass(frozen=True)
class CSTNode:
    node_type: str       # "function", "class", "method", "file"
    name: str            # e.g., "calculate_total"
    full_name: str       # e.g., "MyClass.calculate_total"
    file_path: str       # absolute path
    start_line: int
    end_line: int
    source: str          # actual source code text
    parent_name: str     # enclosing class/module name
    language: str        # "python", "javascript", etc.
```

**Node ID computation** — `compute_node_id(file_path, name, node_type)` returns `SHA256(f"{file_path}:{name}:{node_type}")[:16]`. This is deterministic: the same function at the same path always gets the same 16-char hex ID.

**Discovery flow**: `discover(paths)` uses a thread pool (`max_workers` from config) to parse files in parallel. Each file yields zero or more CSTNodes. Language selection is by file extension. Tree-sitter `.scm` query files define what constitutes a "node" for each language.

### 2.3 Agent Model (AgentNode)

Source: `core/agent_node.py` (279 lines)

`AgentNode` is a **Pydantic BaseModel** that serves as the single representation of an agent throughout the entire system. It has three distinct interfaces:

**Fields** (grouped):

| Group | Fields | Purpose |
|-------|--------|---------|
| Identity | `node_id`, `node_type`, `name`, `full_name`, `language` | Unique identification |
| Graph context | `graph_id`, `file_path`, `start_line`, `end_line`, `parent_id` | Location in codebase |
| Runtime state | `status` (idle/running/error/orphaned), `last_run`, `run_count`, `error_message` | Current execution state |
| Specialization | `bundle`, `model`, `system_prompt_override`, `tool_filter`, `tags`, `metadata` | Per-agent customization (set by extensions) |

**Triple interface**:

1. **SQLite** — `to_row()` returns a dict suitable for `INSERT`/`UPDATE`. `from_row(row)` class method constructs from a SQLite row dict. This is how agents persist in the `nodes` table.

2. **LLM prompt** — `to_system_prompt()` generates a markdown string that becomes the system prompt for the agent's LLM call. Includes the agent's identity, its source code, its file context, and any custom instructions from extensions.

3. **LSP protocol** — `to_code_lens()` returns CodeLens objects for Neovim (clickable annotations above functions). `to_hover()` returns hover information. `to_code_actions()` returns available actions. `to_document_symbol()` returns symbol information. All return `lsp`-typed objects.

### 2.4 Subscriptions & Reactive Routing

Source: `core/subscriptions.py` (320 lines)

The subscription system determines **which agents should run** in response to which events.

**SubscriptionPattern** — defines a filter:
```python
@dataclass
class SubscriptionPattern:
    event_types: tuple[str, ...] | None = None  # e.g., ("ContentChangedEvent",)
    from_agents: tuple[str, ...] | None = None  # filter by source agent
    to_agent: str | None = None                 # filter by target agent
    path_glob: str | None = None                # file path glob pattern
    tags: tuple[str, ...] | None = None         # event tag filter
```

All fields are optional. `None` means "match all". Multiple fields are ANDed together.

**SubscriptionRegistry** — SQLite-backed with an in-memory cache:
- `register(agent_id, pattern)` — persists a subscription
- `unregister(agent_id, pattern_id)` — removes one
- `get_matching_agents(event)` — returns all agent IDs whose subscriptions match the given event
- `register_defaults(agent_id, file_path)` — creates default subscriptions for a newly discovered agent (typically: `ContentChangedEvent` for its own file, `AgentMessageEvent` addressed to it)

The in-memory cache is rebuilt on `initialize()` and kept in sync on mutations. This avoids hitting SQLite on every event match.

### 2.5 Projections

Source: `core/projections.py` (144 lines)

**NodeProjection** transforms the event log into a materialized `nodes` table. It runs inside `EventStore.append()` in the same transaction as the event INSERT.

Rules:
- `NodeDiscoveredEvent` → UPSERT into `nodes` (creates or updates the agent's row)
- `NodeRemovedEvent` → DELETE from `nodes`
- `AgentStartEvent` → set `status = "running"`
- `AgentCompleteEvent` → set `status = "idle"`, increment `run_count`
- `AgentErrorEvent` → set `status = "error"`, store `error_message`

It also applies **extension config matching**: when a node is discovered, it checks all loaded `AgentExtension` classes and applies the first match's `get_extension_data()` overrides (bundle, model, tags, etc.) to the agent's row.

### 2.6 Workspace & Cairn Integration

Source: `core/workspace.py` (191 lines), `core/cairn_bridge.py` (213 lines), `core/cairn_externals.py` (71 lines)

Remora uses **Cairn** for file workspace management. Cairn provides SQLite-backed virtual filesystems with copy-on-write isolation.

**CairnWorkspaceService** (`cairn_bridge.py`):
- `initialize()` — creates `stable.db` (the project's file index), syncs all project files into it via mtime tracking
- `get_agent_workspace(agent_id)` — creates an agent-specific `workspace.db` with CoW isolation from `stable.db`. Each agent gets its own sandbox.
- `get_externals()` — builds a `CairnExternals` dict that Grail tools use for file operations
- Incremental sync: only re-indexes files whose mtime has changed

**CairnExternals** (`cairn_externals.py`):
- Wraps Cairn's external functions with path normalization
- Methods: `read_file`, `write_file`, `list_dir`, `file_exists`, `search_files`, `search_content`, `submit_result`, `log`
- `as_externals()` returns a plain dict suitable for passing to Grail's execution engine

**AgentWorkspace** (`workspace.py`):
- Higher-level wrapper around Cairn with agent-specific methods
- `CairnDataProvider` loads files from the workspace for Grail script execution

### 2.7 Executor (SwarmExecutor)

Source: `core/swarm_executor.py` (396 lines)

Runs a single agent turn. Creates the LLM client once (connection pooling across turns).

**`run_agent(node, trigger_event)`** flow:
1. Resolves the agent's **bundle path** (from `.remora/bundles/` or config mapping)
2. Loads the bundle **manifest** (what tools, what prompt template)
3. Initializes the **workspace** via CairnWorkspaceService
4. Builds **externals** dict: `emit_event`, `register_subscription`, `unsubscribe`, `broadcast`, `query_agents` — these are the swarm communication primitives agents can call from Grail scripts
5. Loads files via `CairnDataProvider`
6. Builds **chat history** from EventStore (previous messages for this agent)
7. Builds the **prompt** — a markdown document containing: target info, source code, trigger event details, chat history
8. Discovers **Grail tools** — `.pym` scripts from the bundle directory
9. Runs the **AgentKernel** (from `structured_agents`) with the prompt and tools
10. Extracts and returns the response

### 2.8 Extensions

Source: `extensions.py` (125 lines)

Extensions customize agent behavior without modifying core code. They live in `.remora/models/*.py`.

**AgentExtension** base class:
```python
class AgentExtension:
    @staticmethod
    def matches(node_type, name, *, file_path="", source_code="") -> bool: ...
    @staticmethod
    def get_extension_data() -> dict: ...
```

**Loading**: `load_extensions(models_dir)` scans `.py` files alphabetically, imports each module, finds all `AgentExtension` subclasses. Uses mtime-based caching to avoid reloading unchanged files.

**Priority**: First match wins. Name files like `00_specific.py`, `50_generic.py` to control ordering.

**Application**: During `NodeProjection.apply()`, when a `NodeDiscoveredEvent` arrives, extensions are checked. The first matching extension's `get_extension_data()` dict is merged into the agent's row (overriding fields like `bundle`, `model`, `tags`, etc.).

### 2.9 Configuration

Source: `core/config.py` (170 lines)

`Config` is a flat **dataclass with `slots=True`**. Loaded from `remora.yaml` via `load_config()`.

| Group | Fields |
|-------|--------|
| Discovery | `paths`, `languages`, `max_workers` |
| Bundles | `root`, `mapping`, `mapping_tools` |
| Model | `base_url`, `default`, `api_key` |
| Swarm | `root`, `id`, `max_concurrency`, `max_turns`, `truncation_limit`, `timeout`, `max_trigger_depth`, `trigger_cooldown_ms`, `chat_history_limit` |
| Workspace | `ignore_patterns`, `ignore_dotfiles` |
| Neovim | `enabled`, `socket` |

### 2.10 Error Hierarchy

Source: `core/errors.py` (60 lines)

```
RemoraError (base)
├── ConfigError        — Config loading/validation failures
├── DiscoveryError     — Tree-sitter parsing failures
├── GraphError         — Graph topology errors
├── ExecutionError     — Agent execution failures
├── WorkspaceError     — Cairn workspace failures
└── SwarmError         — Swarm-level coordination errors
```

---

## 3. The Data Flow Pipeline

This section traces data end-to-end: from source code on disk, through discovery, into the event store, through projections into materialized agent state, through subscription matching into the trigger queue, and finally into an agent turn.

### 3.1 Source Code to CSTNode

```
source file (.py, .js, .ts, .go, .rs, .md, .toml, .yaml, .json)
    │
    ▼
tree-sitter parser (language-specific .scm query file)
    │
    ▼
CSTNode(node_type, name, full_name, file_path, start_line, end_line, source, parent_name, language)
    │
    ▼
compute_node_id(file_path, name, node_type) → SHA256[:16] hex string
```

**What happens**: `discover(paths)` walks the given directory paths, filters by configured languages, and parses each file using the appropriate tree-sitter grammar. The `.scm` query files define what constitutes a "node" — for Python this means functions, classes, and methods. Each match produces a `CSTNode` with its full source text extracted.

**Node ID stability**: The ID is a hash of `file_path:name:node_type`. This means:
- Renaming a function changes its ID (it becomes a new agent)
- Moving a function to a different file changes its ID
- Modifying a function's body does NOT change its ID (same path, same name, same type)

**In LSP mode**: The `ASTWatcher` in the LSP layer does the same thing but also **injects ID comments** (`# rm_xxxx`) into the source file. This is how the LSP server tracks which agent corresponds to which code region, even as the user edits.

### 3.2 CSTNode to EventStore

```
CSTNode
    │
    ▼
NodeDiscoveredEvent(
    node_id=compute_node_id(...),
    node_type="function",
    name="calculate_total",
    full_name="MyClass.calculate_total",
    file_path="/path/to/file.py",
    start_line=10,
    end_line=25,
    source="def calculate_total(self): ...",
    language="python"
)
    │
    ▼
EventStore.append(graph_id, event)
    │
    ├──► events table: INSERT (id, graph_id, "NodeDiscoveredEvent", {json}, timestamp, agent_id)
    │
    ├──► NodeProjection.apply() — same transaction (see 3.3)
    │
    ├──► SubscriptionRegistry.get_matching_agents() — check for triggers (see 3.4)
    │
    └──► EventBus.emit() — in-process notification to subscribers
```

**Serialization**: Events are frozen dataclasses. They're serialized to JSON via `dataclasses.asdict()` for storage. For structured-agents events (which are Pydantic models), `model_dump()` is used instead. Deserialization reconstructs the original event type from the stored `event_type` string and JSON data.

**The transaction boundary**: Steps 1-3 (INSERT, projection, subscription check) happen in a single SQLite transaction. The EventBus emit happens *after* the transaction commits. This ensures that if a subscriber reads the EventStore in response to a notification, the data is already there.

### 3.3 EventStore to AgentNode

```
NodeDiscoveredEvent arrives in NodeProjection.apply()
    │
    ├──► Check extensions: load_extensions(".remora/models/")
    │    For each extension, call extension.matches(node_type, name, file_path=..., source_code=...)
    │    First match wins → get_extension_data() → override fields (bundle, model, tags, etc.)
    │
    ▼
UPSERT into nodes table:
    node_id, node_type, name, full_name, file_path, start_line, end_line,
    source, language, status="idle", graph_id, parent_id,
    bundle, model, system_prompt_override, tool_filter, tags, metadata

Later, when needed:
    row = event_store.get_node(node_id)
    agent = AgentNode.from_row(row)
    # agent is now a fully hydrated Pydantic model
```

**AgentNode.from_row()** handles type coercion: JSON strings are parsed back to dicts/lists, None values get defaults, and the Pydantic validator ensures everything is consistent.

**When status changes**: Subsequent events update the same row:
- `AgentStartEvent` → `UPDATE nodes SET status='running' WHERE node_id=?`
- `AgentCompleteEvent` → `UPDATE nodes SET status='idle', run_count=run_count+1 WHERE node_id=?`
- `AgentErrorEvent` → `UPDATE nodes SET status='error', error_message=? WHERE node_id=?`
- `NodeRemovedEvent` → `DELETE FROM nodes WHERE node_id=?`

### 3.4 Event to Trigger

```
Any event arrives in EventStore.append()
    │
    ▼
SubscriptionRegistry.get_matching_agents(event)
    │
    ├──► For each registered subscription pattern:
    │    - Does event_type match pattern.event_types? (or pattern is None = match all)
    │    - Does event.from_agent match pattern.from_agents?
    │    - Does event target match pattern.to_agent?
    │    - Does event path match pattern.path_glob? (fnmatch)
    │    - Do event tags intersect pattern.tags?
    │    All non-None fields must match (AND logic).
    │
    ▼
Set of matching agent_ids
    │
    ▼
Trigger queue (in-memory deque on EventStore)
    Each entry: (agent_id, trigger_event)
```

**Default subscriptions** (registered by `register_defaults()`):
- Every agent subscribes to `ContentChangedEvent` for its own file path
- Every agent subscribes to `AgentMessageEvent` addressed to it (via `to_agent` field)

**Custom subscriptions** can be registered by agents themselves at runtime using the `register_subscription` external provided by SwarmExecutor, or via the `SubscribeTool` in swarm tools.

### 3.5 Trigger to Agent Turn

```
Trigger queue entry: (agent_id, trigger_event)
    │
    ▼
Cascade prevention check:
    - trigger_depth < max_trigger_depth? (default: typically 3-5)
    - cooldown elapsed since last run? (trigger_cooldown_ms)
    - concurrency semaphore available? (max_concurrency)
    │
    ▼
SwarmExecutor.run_agent(node, trigger_event)  OR  AgentRunner.execute_turn(agent_id, trigger)
    │
    ├──► Resolve bundle path
    ├──► Load manifest
    ├──► Initialize workspace (Cairn)
    ├──► Build externals dict
    ├──► Load files (CairnDataProvider)
    ├──► Build chat history from EventStore
    ├──► Build prompt (markdown: target info + code + trigger + history)
    ├──► Discover Grail tools (.pym scripts)
    ├──► Run AgentKernel (LLM interaction with tool loop, max 5 rounds)
    │
    ▼
AgentCompleteEvent or AgentErrorEvent
    │
    └──► Back to EventStore.append() → may trigger more agents (cascade)
```

**Cascade prevention** is critical. Without it, agent A could trigger agent B, which triggers agent A, ad infinitum. The `max_trigger_depth` config controls how deep cascades can go. The `trigger_cooldown_ms` prevents rapid re-triggering. These are enforced in both `SwarmExecutor` and `AgentRunner`.

---

## 4. Neovim Demo Architecture

Source: `remora/src/remora/lsp/`

The Neovim demo surfaces Remora as a **Language Server Protocol (LSP) server**. Every function/class in the user's code appears as an agent with code lenses, hover info, code actions, and diagnostic annotations. The user interacts with agents through Neovim's native LSP UI.

### 4.1 LSP Server Structure

Source: `lsp/server.py` (171 lines), `lsp/__main__.py` (251 lines)

**`RemoraLanguageServer`** extends `pygls.LanguageServer`. It holds:
- `db: RemoraDB` — LSP-specific SQLite database (`indexer.db`)
- `graph: LazyGraph` — graph topology engine (backed by rustworkx)
- `watcher: ASTWatcher` — tree-sitter file parser
- `proposals: dict` — pending rewrite proposals by agent_id
- `runner: AgentRunner` — the agent execution coordinator (set after initialization)

**Global singleton pattern**: A module-level `server` instance is created. `register_handlers(server)` attaches all LSP handlers (document events, hover, code lens, commands, etc.) to this singleton.

**Custom methods on the server**:
- `generate_correlation_id()` — UUID for tracking request/response pairs
- `refresh_code_lenses()` — tells Neovim to re-request code lenses
- `publish_diagnostics(uri, diagnostics)` — pushes diagnostic annotations to Neovim
- `emit_event(event)` — appends to EventStore AND notifies the Neovim client via `$/remora/event`
- `discover_tools_for_agent(agent_id)` — finds Grail tools available to a specific agent
- `notify_agents_updated()` — sends `$/remora/agentsUpdated` to the client

**Startup flow** (`__main__.py`):
1. Load config
2. Create LLM client (structured_agents)
3. Create AgentRunner with event_store, subscriptions, LLM client
4. Attach runner to server
5. On `INITIALIZED`:
   - Start `runner.run_forever()` as background asyncio task
   - Start `_background_scan()` — walks the workspace, parses all source files, emits NodeDiscoveredEvents for everything found

### 4.2 AgentRunner

Source: `lsp/runner.py` (840 lines)

The **unified async agent execution coordinator**. This is the most complex single file in the codebase.

**`LLMClient`** — adapter wrapping the `structured_agents` client. Provides `create_kernel()` for creating AgentKernel instances.

**`Trigger`** — Pydantic model: `agent_id: str`, `event: RemoraEvent | None`, `depth: int = 0`, `feedback: str | None = None`.

**Cascade prevention**:
- `max_trigger_depth` — maximum depth of trigger chains (default from config)
- `trigger_cooldown_ms` — minimum time between consecutive runs of the same agent
- `asyncio.Semaphore` — caps concurrent agent executions

**`run_forever()` loop**:
```python
while self._running:
    trigger = await self._trigger_queue.get()
    if trigger.depth > self.max_trigger_depth:
        continue  # cascade limit
    if not cooldown_elapsed(trigger.agent_id):
        continue  # too soon
    async with self._semaphore:
        await self.execute_turn(trigger)
```

**`poll_command_queue()`** — reads from the `command_queue` table in RemoraDB. This is how external systems (web frontend, CLI) inject work into the runner. Polls on an interval, converts command rows into Triggers, pushes them onto the trigger queue.

**`execute_turn(trigger)`** flow:
1. Load agent from EventStore's `nodes` table → `AgentNode.from_row()`
2. Apply extensions (check for overrides)
3. Build messages:
   - **System prompt**: `agent.to_system_prompt()` (markdown with identity, code, instructions)
   - **Correlation events**: recent events from EventStore that involved this agent
   - **Rejection feedback**: if this turn was triggered by a proposal rejection, include the user's feedback
4. **Tool call loop** (max 5 rounds):
   - Send messages to LLM via AgentKernel
   - If response contains tool calls, execute them via `handle_response()`
   - Available tools: `rewrite_self`, `message_node`, `read_node`
   - Append tool results to messages, loop again
5. Emit `AgentCompleteEvent` or `AgentErrorEvent`

**`create_proposal(agent_id, new_source)`** — creates a `RewriteProposal`, stores it in RemoraDB, publishes diagnostics (yellow squiggly lines) to Neovim showing the proposed diff.

**`create_headless()`** — factory for CLI mode. Creates an AgentRunner without an LSP server reference, suitable for `remora swarm start` (no Neovim).

### 4.3 RemoraDB (indexer.db)

Source: `lsp/db.py` (257 lines)

LSP-specific SQLite database, separate from the core EventStore. Uses WAL mode for concurrent access.

**Tables**:

| Table | Columns | Purpose |
|-------|---------|---------|
| `edges` | `source_id`, `target_id`, `edge_type`, `weight` | Code dependency graph (calls, imports, inheritance) |
| `activation_chain` | `id`, `agent_id`, `parent_id`, `depth`, `timestamp` | Tracks trigger cascade chains |
| `proposals` | `id`, `agent_id`, `original_source`, `proposed_source`, `diff`, `status`, `created_at` | Rewrite proposals pending user review |
| `cursor_focus` | `id`, `file_path`, `line`, `character`, `agent_id`, `timestamp` | Current cursor position in Neovim (for web graph highlighting) |
| `command_queue` | `id`, `command_type`, `payload` (JSON), `status`, `created_at` | Commands from external systems waiting for the runner to process |

**Key crossover**: `command_queue` is the bridge between the web frontend and the LSP runner. The web UI inserts rows; `AgentRunner.poll_command_queue()` reads and processes them.

**Key crossover**: `cursor_focus` is the bridge between Neovim cursor position and the web graph viewer. The `$/remora/cursorMoved` notification updates this table; the graph viewer reads it to highlight the focused agent.

### 4.4 LazyGraph

Source: `lsp/graph.py` (199 lines)

Graph topology engine backed by **rustworkx** (Rust-based graph library, fast).

**Design**: The full graph of all agents and their edges could be large. LazyGraph only loads the **neighborhood** around the agents being accessed. It uses a **recursive CTE SQL query** against the `edges` table in RemoraDB to walk the graph outward from a given node.

**API**:
- `invalidate()` — marks the in-memory graph as stale (called after file saves that may change edges)
- `ensure_loaded(node_id)` — loads the neighborhood if not already cached
- `get_parent(node_id)` — returns the parent node (class for a method, module for a function)
- `get_callers(node_id)` — returns nodes that call this one

**Data source**: Edges are populated by `ASTWatcher` during file parsing — it detects function calls, class inheritance, and imports, then inserts them into the `edges` table.

### 4.5 ASTWatcher

Source: `lsp/watcher.py` (293 lines)

Parses source files and manages agent identity across edits.

**`parse_and_inject_ids(file_path)`**:
1. Parse the file with tree-sitter (Python-specific: functions, classes, methods)
2. For each discovered node, compute its stable ID (`compute_node_id()`)
3. **Inject ID comments** into the source: `# rm_abcdef1234567890` at the end of the def/class line
4. Non-Python files get file-level nodes only (no injection)

**ID preservation**: When a file is re-parsed after edits, existing `# rm_xxxx` comments are detected and the same IDs are reused. This ensures agent identity is stable across edits even if the function moves within the file.

**Fallback**: When tree-sitter is unavailable, a regex-based parser handles basic Python function/class detection.

**Edge detection**: During parsing, the watcher also identifies call relationships between functions (by analyzing the AST for function call nodes) and inserts them into the `edges` table via RemoraDB.

### 4.6 Proposals & Rewrites

Source: `lsp/models.py` (255 lines)

The proposal system is how agents suggest code changes to the user.

**`RewriteProposal`** — Pydantic model:
```python
class RewriteProposal(BaseModel):
    id: str
    agent_id: str
    original_source: str
    proposed_source: str
    file_path: str
    start_line: int
    end_line: int
    status: str  # "pending", "accepted", "rejected"
```

**Computed properties**:
- `diff` — unified diff between original and proposed source
- `to_workspace_edit()` — converts to LSP `WorkspaceEdit` (what Neovim applies when user accepts)
- `to_diagnostic()` — converts to LSP `Diagnostic` (yellow squiggly line showing the diff in the gutter)
- `to_code_actions()` — returns "Accept" and "Reject" code actions for the Neovim UI

**Lifecycle**:
1. Agent calls `rewrite_self` tool with new source code
2. Runner calls `create_proposal()` → stores in RemoraDB, publishes diagnostic
3. User sees yellow annotation in Neovim with the proposed diff
4. User triggers code action: "Accept Proposal" → applies workspace edit, removes diagnostic
5. OR user triggers "Reject Proposal" → prompts for feedback, triggers a new agent turn with rejection feedback

**Event models** (`lsp/models.py`): `HumanChatEvent`, `AgentMessageEvent`, `RewriteProposalEvent`, `RewriteAppliedEvent`, `RewriteRejectedEvent`, `AgentErrorEvent`. Each has a `to_core_event()` method for converting to the core event types.

### 4.7 LSP Handlers

Source: `lsp/handlers/` (6 files)

**Document lifecycle** (`documents.py`, 166 lines):
- `did_open`: parse file, emit NodeDiscoveredEvents, update edges, refresh code lenses, load existing proposals
- `did_save`: same as did_open + detect orphaned nodes (NodeRemovedEvent), invalidate graph, inject IDs into source
- `did_close`: clean up proposals for the closed file

**Hover** (`hover.py`, 25 lines): Gets the agent at cursor position, calls `agent.to_hover(events)` which returns agent identity, status, last run info, and recent events.

**Commands** (`commands.py`, 201 lines):
- `remora.getAgentPanel` — returns detailed agent info (tools, events, status)
- `remora.chat` — triggers a human input request (user sends a message to an agent)
- `remora.requestRewrite` — asks an agent to propose a rewrite
- `remora.executeTool` — runs a specific tool for an agent
- `remora.acceptProposal` — applies a workspace edit from a proposal
- `remora.rejectProposal` — triggers feedback input, then re-runs the agent with feedback
- `remora.selectAgent` — selects an agent for interaction
- `remora.messageNode` — sends a message to a specific agent

**Code Actions** (`actions.py`, 32 lines): Returns `agent.to_code_actions()` plus any pending proposal actions.

**Code Lens** (`lens.py`, 34 lines): Returns `agent.to_code_lens()` for every agent in the file — clickable annotations like "Run Agent", "Chat", "View".

**Capabilities** (`capabilities.py`, 17 lines): Initialize handler, logs the connection.

### 4.8 Custom Notifications

Source: `lsp/notifications.py` (93 lines), `lsp/server.py`

These are custom LSP notification methods (prefixed with `$/remora/`) for communication between Neovim and the LSP server:

| Notification | Direction | Payload | Purpose |
|-------------|-----------|---------|---------|
| `$/remora/cursorMoved` | Client → Server | `{file_path, line, character}` | Updates `cursor_focus` table in RemoraDB. Web graph uses this to highlight the focused agent. |
| `$/remora/submitInput` | Client → Server | `{agent_id, content}` or `{agent_id, rejection_feedback}` | Handles chat messages and proposal rejection feedback. Creates a Trigger and pushes it to the runner's queue. |
| `$/remora/event` | Server → Client | Serialized event | Notifies Neovim that an event occurred (for status bar updates, etc.). |
| `$/remora/agentsUpdated` | Server → Client | `{agents: [...]}` | Notifies that the agent list changed (after discovery or node removal). |

### 4.9 Agent Tools in Neovim Context

Source: `lsp/runner.py` (within `execute_turn`)

In the Neovim context, agents have three specialized tools:

**`rewrite_self`** — The agent proposes new source code for itself. The runner creates a `RewriteProposal`, stores it in RemoraDB, and publishes a diagnostic to Neovim. The user sees the diff and can accept or reject.

**`message_node`** — The agent sends a message to another agent (by node_id). This creates an `AgentMessageEvent` and pushes a Trigger for the target agent onto the queue.

**`read_node`** — The agent reads the current source code of another agent (by node_id). Returns the source text from the EventStore's nodes table.

---

## 5. Web Demo Architecture

The web demo has two independent parts: (1) **Remora's built-in service layer** (Starlette + Datastar dashboard), and (2) the **Graph Viewer** (this repo's Stario frontend). They can run simultaneously but are separate processes that share state through SQLite.

### 5.1 Service Layer (RemoraService)

Source: `service/api.py` (200 lines), `service/handlers.py` (145 lines)

**`RemoraService`** is a framework-agnostic API class. It wires together the core components and exposes methods that HTTP adapters can call.

**`create_default(config, project_root)`** factory:
1. Creates EventBus, EventStore, SubscriptionRegistry, NodeProjection
2. Initializes all databases
3. Creates UiStateProjector
4. Subscribes UiStateProjector to EventBus (so UI state updates in real-time)
5. Returns a configured `RemoraService` instance

**Key methods**:

| Method | Returns | Purpose |
|--------|---------|---------|
| `index_html()` | HTML string | Full Datastar dashboard page |
| `subscribe_stream()` | Async SSE generator | Datastar SSE patches (live UI updates) |
| `events_stream()` | Async SSE generator | Raw event SSE (for non-Datastar consumers) |
| `replay_events(graph_id)` | Async SSE generator | Historical event replay with optional follow mode |
| `input(request_id, response)` | None | Submit human input response |
| `config_snapshot()` | dict | Current config as JSON |
| `ui_snapshot()` | dict | Current UiStateProjector snapshot |
| `emit_event(event_data)` | None | Inject an event into the system |
| `list_agents()` | list[dict] | All agents from EventStore |
| `get_agent(agent_id)` | dict | Single agent details |
| `get_agent_subscriptions(agent_id)` | list[dict] | Agent's subscription patterns |

**ServiceDeps** (`handlers.py`): A dataclass bundling all dependencies (event_store, event_bus, subscriptions, ui_projector) that handlers need.

**Handlers** (`handlers.py`):
- `handle_input()` — resolves a blocked HumanInputRequestEvent by emitting HumanInputResponseEvent
- `handle_config_snapshot()` — returns current config
- `handle_ui_snapshot()` — returns UiStateProjector.snapshot()
- `handle_swarm_emit()` — creates and appends AgentMessageEvent or ContentChangedEvent
- `handle_swarm_list_agents()` / `handle_swarm_get_agent()` — reads from EventStore nodes table
- `handle_swarm_get_subscriptions()` — reads from SubscriptionRegistry

### 5.2 Starlette Adapter

Source: `adapters/starlette.py` (138 lines)

Translates `RemoraService` methods into HTTP routes using Starlette.

**Route table**:

| Method | Path | Handler | Response |
|--------|------|---------|----------|
| GET | `/` | `index_html()` | Full HTML page |
| GET | `/subscribe` | `subscribe_stream()` | Datastar SSE (DatastarResponse) |
| GET | `/events` | `events_stream()` | Raw SSE |
| GET | `/replay` | `replay_events()` | SSE with optional follow mode |
| POST | `/input` | `input()` | JSON `{request_id, response}` |
| GET | `/config` | `config_snapshot()` | JSON |
| GET | `/snapshot` | `ui_snapshot()` | JSON |
| GET | `/swarm/agents` | `list_agents()` | JSON array |
| GET | `/swarm/agents/{id}` | `get_agent()` | JSON |
| POST | `/swarm/events` | `emit_event()` | JSON `{event_type, ...data}` |
| GET | `/swarm/subscriptions/{id}` | `get_agent_subscriptions()` | JSON array |

**DatastarResponse**: A special Starlette response class that sets the correct SSE headers and content type for Datastar's `data-on-load="@get('/subscribe')"` pattern.

### 5.3 Datastar Integration

Source: `service/datastar.py` (68 lines)

Datastar is a hypermedia framework that updates the DOM via SSE patches. The server sends HTML fragments; Datastar swaps them into the page.

**`render_shell(body_html)`** — generates the full HTML page:
```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/@starfederation/datastar"></script>
    <style>/* dashboard CSS */</style>
</head>
<body data-on-load="@get('/subscribe')">
    {body_html}
</body>
</html>
```

The `data-on-load="@get('/subscribe')"` attribute tells Datastar to immediately open an SSE connection to `/subscribe` when the page loads.

**`render_patch(selector, html)`** — generates an SSE message that Datastar interprets:
```
event: datastar-merge-patches
data: selector #remora-root
data: merge morph
data: fragment <main id="remora-root">...new HTML...</main>

```

**`render_signals(signals_dict)`** — generates an SSE message that updates Datastar's client-side signals (reactive state).

**Update cycle**:
1. EventBus emits an event
2. UiStateProjector.record() updates the snapshot
3. subscribe_stream() yields a new `render_patch()` with the re-rendered dashboard HTML
4. Browser receives SSE → Datastar morphs the DOM

### 5.4 UI Layer

Source: `ui/projector.py` (204 lines), `ui/view.py` (118 lines), `ui/components/` (5 files)

**UiStateProjector** (`projector.py`):
Reduces the event stream into a JSON-serializable UI state. Tracks:
- `events` — deque of last 200 normalized event envelopes (with kind, type, graph_id, agent_id, timestamp, payload)
- `blocked` — dict of agents waiting for human input (keyed by request_id)
- `agent_states` — dict of agent_id → {state, name}
- `results` — list of agent completion results
- `progress` — {total, completed, failed} counters
- `recent_targets` — deque of last 10 target paths

`record(event)` processes each event and updates the appropriate state. `snapshot()` returns the full state dict.

**`normalize_event(event)`** — converts any event (dataclass or Pydantic) into a uniform dict:
```python
{"kind": "agent", "type": "AgentStartEvent", "graph_id": "...", "agent_id": "...", "timestamp": 1234.5, "payload": {...}}
```

**Component system** (`ui/components/`):
- `Component` (ABC) — abstract base, `render() → str`
- `Element` — generic HTML tag with id, class, attrs, data-attrs
- `RawHTML` — passthrough (no escaping)
- Layout: `Card`, `Container`, `FlexRow`, `Grid`, `Panel`
- Controls: `Button`, `Input`, `Select`
- Data: `List`, `ListItem`, `ProgressBar`, `StatusBadge`
- Dashboard: `EventsList`, `AgentStatusList`, `BlockedAgentCard`, `GraphLauncher`, `ResultsList`

**`render_dashboard(state)`** (`view.py`) — composes all components into a full dashboard HTML string from the projector snapshot.

### 5.5 ChatService

Source: `service/chat_service.py` (254 lines)

A **standalone Starlette application** for single-agent chat interactions. Separate from the main Remora service — can run independently.

**Routes**:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/sessions` | Create a new chat session (returns session_id) |
| DELETE | `/sessions/{id}` | Delete a session |
| POST | `/sessions/{id}/messages` | Send a message to an agent |
| GET | `/sessions/{id}/history` | Get chat history |
| GET | `/sessions/{id}/events` | SSE stream of ToolCall/ToolResult events for this session |
| GET | `/tools` | List available tools |
| GET | `/health` | Health check |

**`ChatSession`** (`core/chat.py`, 280 lines):
- Wraps single-agent interaction with `ChatConfig`, `Message`, `AgentResponse`
- `send(content)` builds kernel messages, runs via AgentKernel, returns response
- `build_chat_tools()` creates file operation tools: `read_file`, `write_file`, `list_dir`, `file_exists`, `search_files`, `discover_symbols`

**Architecture**: Uses module-level singleton state (dict of session_id → ChatSession). SSE streaming pushes ToolCall/ToolResult events to the client as they happen during the LLM interaction.

### 5.6 Graph Viewer (remora-demo frontend)

Source: `remora-demo/frontend/graph/` (13 source files, 132 tests)

The **Graph Viewer** is a standalone Stario web application in *this repo*. It connects to Remora's `events.db` read-only and renders an interactive SVG force-directed graph of agents.

**Architecture**:
```
events.db (SQLite WAL, read-only)
    │
    ▼
GraphState — reads nodes and events tables
    │
    ▼
DBBridge — polls SQLite fingerprints on interval, publishes changes to Relay
    │
    ▼
Relay (Stario's pub/sub) → SSE to browser
    │
    ▼
Browser renders SVG via Datastar morphing
```

**GraphState** (`graph/state.py`):
- Opens `events.db` in read-only mode with WAL
- `load_snapshot()` → `GraphSnapshot` with nodes, edges, metadata
- Computes a fingerprint (hash of table modification counters) to detect changes
- Pure reads — never writes to the database

**DBBridge** (`graph/bridge.py`):
- Runs on an async interval (configurable polling period)
- Calls `GraphState.load_snapshot()`, compares fingerprint to last known
- If changed, publishes the new snapshot to Stario's `Relay`
- Relay fans out to all connected SSE clients

**Layout engine** (`graph/layout.py`):
- Force-directed graph layout algorithm
- Runs on the server side (not in the browser)
- Takes nodes + edges, produces x/y coordinates for each node

**SVG rendering** (`graph/svg.py`):
- Builds SVG elements as f-strings (Stario has no SVG component support)
- Nodes are circles with labels, edges are lines
- Produces the full `<svg>` string for a graph snapshot

**Stario app** (`graph/app.py`):
- App factory: creates routes, initializes DBBridge
- Routes serve the shell page, handle SSE subscriptions
- Uses Stario's `Writer` for SSE responses and `Relay` for pub/sub

**Views** (`graph/views/`):
- `shell.py` — full HTML page with Datastar
- `graph.py` — SVG graph rendering
- `sidebar.py` — agent details panel
- `event_stream.py` — event list rendering

---

## 6. Crossover Interfaces

This is the core of this document. Every boundary where data crosses between subsystems is documented here with the exact data shapes, serialization format, and gotchas.

### 6.1 Event Serialization Boundary

**Boundary**: In-memory event object ↔ SQLite `events` table

**Direction**: Bidirectional (write on append, read on replay/query)

**Write path** (`EventStore.append()`):
```python
# Frozen dataclass events:
event_data = json.dumps(dataclasses.asdict(event))

# Pydantic model events (structured_agents):
event_data = json.dumps(event.model_dump())

# Stored as:
INSERT INTO events (graph_id, event_type, event_data, timestamp, agent_id)
VALUES (?, type(event).__name__, event_data_json, event.timestamp, event.agent_id)
```

**Read path** (`EventStore.replay()`, `get_recent_events()`):
```python
row = cursor.fetchone()
event_type = row["event_type"]  # e.g., "AgentStartEvent"
event_data = json.loads(row["event_data"])  # dict
event = EVENT_TYPE_MAP[event_type](**event_data)  # reconstruct
```

**Data shape in SQLite**:
- `event_type`: string, the class name (e.g., `"NodeDiscoveredEvent"`)
- `event_data`: JSON string, all fields of the event as a flat dict
- `timestamp`: float, Unix epoch
- `agent_id`: string, may be empty for non-agent events

**Gotchas**:
- Tuple fields in events become JSON arrays. When deserializing, they must be converted back to tuples.
- `None` values are preserved in JSON as `null`.
- Enum values are stored as their `.value` strings.
- Events from `structured_agents` (Pydantic) vs Remora core (dataclass) use different serialization paths.

### 6.2 EventStore to EventBus

**Boundary**: Persistence layer → in-process notification

**Direction**: One-way (EventStore → EventBus)

**When it fires**: After `EventStore.append()` commits the SQLite transaction (INSERT + projection + subscription check), it calls `self.event_bus.emit(event)`.

**What crosses**: The original in-memory event object (not a copy, not re-deserialized). This is the same Python object that was passed to `append()`.

**Subscriber types**:
- `UiStateProjector.record()` — updates the UI snapshot
- User-registered handlers via `bus.subscribe()`
- Stream consumers via `bus.stream()`

**Gotchas**:
- The emit happens *outside* the SQLite transaction. If a subscriber reads the EventStore in response, the data is already committed.
- If a subscriber raises an exception with `error_policy="log"` (default), the error is logged but other subscribers still fire.
- The EventBus is in-process only. If the LSP server and web service are separate processes, they do NOT share an EventBus. They must poll SQLite independently.

### 6.3 EventStore to SubscriptionRegistry to Trigger Queue

**Boundary**: Event persistence → reactive agent scheduling

**Direction**: One-way pipeline within `EventStore.append()`

**Flow inside the transaction**:
```python
# Inside EventStore.append(), after INSERT and projection:
matching_agents = self.subscriptions.get_matching_agents(event)
for agent_id in matching_agents:
    self._trigger_queue.append((agent_id, event))
```

**What crosses**:
- `get_matching_agents()` receives the event object, returns a `set[str]` of agent_ids
- Each `(agent_id, event)` tuple is pushed onto the in-memory trigger deque
- The trigger queue is consumed by `SwarmExecutor` or `AgentRunner` in their run loop

**Subscription matching logic**:
```python
def matches(pattern: SubscriptionPattern, event: RemoraEvent) -> bool:
    if pattern.event_types and type(event).__name__ not in pattern.event_types:
        return False
    if pattern.from_agents and getattr(event, 'from_agent', None) not in pattern.from_agents:
        return False
    if pattern.to_agent and getattr(event, 'to_agent', None) != pattern.to_agent:
        return False
    if pattern.path_glob and not fnmatch(getattr(event, 'path', ''), pattern.path_glob):
        return False
    if pattern.tags and not set(pattern.tags) & set(getattr(event, 'tags', ())):
        return False
    return True
```

**Gotchas**:
- The subscription check happens inside the SQLite transaction but the trigger queue is in-memory. If the process crashes between transaction commit and trigger consumption, triggers are lost. This is acceptable because reconciliation on restart will re-discover everything.
- The in-memory cache in SubscriptionRegistry is critical for performance. Without it, every `append()` would hit SQLite twice (once for the event, once for matching subscriptions).

### 6.4 AgentNode Triple Interface

**Boundary**: One model, three serialization targets

**1. SQLite (persistence)**:
```python
# Write:
row = agent.to_row()  # → dict with string keys, JSON-serializable values
# Fields: node_id, node_type, name, full_name, file_path, start_line, end_line,
#          source, language, status, graph_id, parent_id, bundle, model,
#          system_prompt_override, tool_filter, tags (JSON array), metadata (JSON dict),
#          last_run, run_count, error_message

# Read:
agent = AgentNode.from_row(row_dict)
# Handles: JSON string → dict/list coercion, None defaults, type validation
```

**2. LLM Prompt**:
```python
prompt = agent.to_system_prompt()
# Returns markdown string:
# ## Agent: {name}
# Type: {node_type} | Language: {language}
# File: {file_path} (lines {start_line}-{end_line})
#
# ### Source Code
# ```{language}
# {source}
# ```
#
# ### Instructions
# {system_prompt_override or default instructions}
```

**3. LSP Protocol**:
```python
agent.to_code_lens()       # → list[lsp.CodeLens] — clickable annotations
agent.to_hover(events)     # → lsp.Hover — tooltip with agent info + recent events
agent.to_code_actions()    # → list[lsp.CodeAction] — context menu items
agent.to_document_symbol() # → lsp.DocumentSymbol — outline entry
```

**Gotchas**:
- `to_row()` serializes `tags` (tuple) and `metadata` (dict) to JSON strings. `from_row()` deserializes them back.
- `to_system_prompt()` truncates the source code if it exceeds the configured `truncation_limit`.
- LSP methods import from `lsp` types lazily (the `lsp` module reference is resolved at call time, not import time).

### 6.5 SQLite as Shared State Bus

**Boundary**: Multiple OS processes sharing state via filesystem

**Mechanism**: All SQLite databases use **WAL (Write-Ahead Logging) mode**. This allows:
- Multiple readers simultaneously
- One writer at a time (with readers not blocked)
- Readers see a consistent snapshot (isolation)

**Who shares what**:

| Database | Writer(s) | Reader(s) |
|----------|-----------|-----------|
| `events.db` | LSP server (EventStore), CLI swarm | Web service (RemoraService), Graph viewer (GraphState) |
| `indexer.db` | LSP server (RemoraDB) | Web frontend (via command_queue writes), Graph viewer (cursor_focus reads) |
| `subscriptions.db` | LSP server, CLI swarm | (same process typically) |
| `agents.db` | SwarmState (any process with swarm_executor) | (same process typically) |

**Gotchas**:
- WAL mode requires the writer and all readers to be on the **same filesystem**. Network filesystems (NFS, CIFS) will break.
- The WAL file (`events.db-wal`) and shared-memory file (`events.db-shm`) must be accessible to all processes.
- Long-running readers can prevent WAL checkpointing, causing the WAL file to grow. The Graph Viewer's `DBBridge` mitigates this by using short-lived read transactions.
- If the writer crashes mid-transaction, WAL recovery happens automatically on the next open.

### 6.6 command_queue Table

**Boundary**: External system → AgentRunner

**Direction**: Write from web frontend or CLI → Read by AgentRunner.poll_command_queue()

**Schema**:
```sql
CREATE TABLE command_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,     -- e.g., "chat", "rewrite", "trigger"
    payload TEXT NOT NULL,          -- JSON: {agent_id, content, ...}
    status TEXT DEFAULT 'pending',  -- "pending", "processing", "done", "error"
    created_at REAL NOT NULL
);
```

**Data shapes by command_type**:

| command_type | payload shape | What happens |
|-------------|---------------|-------------|
| `"chat"` | `{"agent_id": "abc123", "content": "Please refactor this"}` | Runner creates a Trigger with the chat content as a HumanInputResponseEvent |
| `"rewrite"` | `{"agent_id": "abc123"}` | Runner triggers a rewrite request for the agent |
| `"trigger"` | `{"agent_id": "abc123", "event_type": "ManualTriggerEvent"}` | Runner creates and dispatches a ManualTriggerEvent |

**Polling cycle**:
```python
# In AgentRunner.poll_command_queue():
while self._running:
    rows = await db.get_pending_commands()  # SELECT ... WHERE status='pending' LIMIT 10
    for row in rows:
        await db.mark_command_processing(row["id"])
        trigger = self._command_to_trigger(row)
        await self._trigger_queue.put(trigger)
        await db.mark_command_done(row["id"])
    await asyncio.sleep(poll_interval)
```

**Gotchas**:
- This is an **eventually consistent** interface. There's a polling delay between command insertion and processing.
- If the AgentRunner is not running (e.g., LSP server is down), commands accumulate in the queue.
- Status transitions: `pending → processing → done/error`. A process crash during `processing` leaves the command stuck. Restart should re-check `processing` commands.

### 6.7 cursor_focus Table

**Boundary**: Neovim editor → Web graph viewer

**Direction**: Write from LSP server (on `$/remora/cursorMoved`) → Read by Graph Viewer

**Schema**:
```sql
CREATE TABLE cursor_focus (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    character INTEGER NOT NULL,
    agent_id TEXT,           -- resolved agent at cursor position (may be NULL)
    timestamp REAL NOT NULL
);
```

**Write path**:
1. User moves cursor in Neovim
2. Neovim plugin sends `$/remora/cursorMoved` notification with `{file_path, line, character}`
3. LSP server's notification handler resolves which agent (if any) is at that position
4. UPSERTs into `cursor_focus` table with the resolved `agent_id`

**Read path**:
1. Graph Viewer's `DBBridge` reads `cursor_focus.agent_id` during its polling loop
2. If an agent is focused, the SVG renderer highlights that node in the graph
3. The sidebar shows details for the focused agent

**Gotchas**:
- The `agent_id` may be `NULL` if the cursor is not on any recognized code node.
- There's only one row in this table (it's effectively a key-value store for cursor state).
- The Graph Viewer must handle the case where the `cursor_focus` table doesn't exist (LSP server hasn't started yet).

### 6.8 HTTP/SSE API Boundary

**Boundary**: HTTP client (browser) ↔ Starlette server

**SSE data format (Datastar patches)**:
```
event: datastar-merge-patches
data: selector #remora-root
data: merge morph
data: fragment <main id="remora-root">...full dashboard HTML...</main>

```

Each SSE message is a complete re-render of the dashboard. Datastar's `morph` mode diffs the new HTML against the current DOM and applies minimal changes.

**SSE data format (raw events)**:
```
event: message
data: {"kind": "agent", "type": "AgentStartEvent", "graph_id": "...", "agent_id": "...", "timestamp": 1234.5, "payload": {...}}

```

**REST endpoint data shapes**:

`POST /input`:
```json
{"request_id": "uuid-string", "response": "user's answer text"}
```

`POST /swarm/events`:
```json
{"event_type": "AgentMessageEvent", "from_agent": "cli", "to_agent": "abc123", "content": "hello", "tags": []}
// OR
{"event_type": "ContentChangedEvent", "path": "/path/to/file.py", "diff": "optional diff"}
```

`GET /swarm/agents` response:
```json
[
  {
    "node_id": "abc123def456789",
    "node_type": "function",
    "name": "calculate_total",
    "full_name": "MyClass.calculate_total",
    "file_path": "/path/to/file.py",
    "status": "idle",
    "language": "python",
    "run_count": 3,
    "last_run": 1234567890.0,
    ...
  }
]
```

`GET /snapshot` response:
```json
{
  "events": [{...}, ...],
  "blocked": [{...}, ...],
  "agent_states": {"agent_id": {"state": "started", "name": "func"}},
  "progress": {"total": 10, "completed": 7, "failed": 1},
  "results": [{...}, ...],
  "recent_targets": ["/path/to/file.py", ...]
}
```

### 6.9 DBBridge Polling Loop

**Boundary**: SQLite database → Stario Relay → SSE to browser

**Direction**: One-way (DB → Relay → Browser)

**Mechanism**:
```python
class DBBridge:
    async def poll(self):
        while True:
            snapshot = await asyncio.to_thread(self.state.load_snapshot)
            fingerprint = snapshot.fingerprint
            if fingerprint != self._last_fingerprint:
                self._last_fingerprint = fingerprint
                await self.relay.publish("graph", snapshot)
            await asyncio.sleep(self.poll_interval)
```

**Fingerprint computation**: `GraphState` computes a fingerprint from SQLite's internal page counters or a hash of the nodes table content. This is a cheap operation that avoids reading all rows on every poll.

**What crosses the Relay**:
- A `GraphSnapshot` object containing: list of nodes (with x/y layout coordinates), list of edges, metadata
- The Relay fans this out to all connected SSE clients
- Each client's handler renders the snapshot into SVG HTML and sends it as a Datastar patch

**Gotchas**:
- The poll interval determines latency. Too fast wastes CPU; too slow makes the UI feel laggy. Default is typically 0.5-1 second.
- `asyncio.to_thread` is used for the SQLite read to avoid blocking the event loop.
- The fingerprint avoids sending redundant updates when nothing has changed.
- If the Graph Viewer process starts before the LSP server has created `events.db`, the DBBridge must handle the missing file gracefully.

### 6.10 Cairn Externals Interface

**Boundary**: Grail tool scripts → filesystem (via Cairn workspace)

**Direction**: Bidirectional (read/write files through the workspace)

**What agents call** (available in `.pym` Grail scripts):
```python
# These are injected as externals into the Grail execution context:
externals = {
    "read_file": cairn.read_file,       # (path) → str
    "write_file": cairn.write_file,     # (path, content) → None
    "list_dir": cairn.list_dir,         # (path) → list[str]
    "file_exists": cairn.file_exists,   # (path) → bool
    "search_files": cairn.search_files, # (pattern) → list[str]
    "search_content": cairn.search_content,  # (pattern, path?) → list[{file, line, text}]
    "submit_result": cairn.submit_result,    # (result) → None
    "log": cairn.log,                        # (message) → None
}
```

**Path normalization**: `CairnExternals` normalizes all paths to be relative to the workspace root. Absolute paths are rejected or converted. This prevents agents from escaping their sandbox.

**CoW isolation**: Each agent's workspace is a copy-on-write fork of `stable.db`. Writes go to the agent's `workspace.db` only. The original files are unchanged. This provides isolation between agents and rollback capability.

**Gotchas**:
- The workspace is a **virtual filesystem** backed by SQLite. It's not the actual disk filesystem. Agent writes don't immediately appear on disk.
- `stable.db` is synced from disk on initialization and incrementally via mtime tracking. If a file changes on disk between syncs, the workspace will have stale data.
- The `submit_result` function is how an agent reports its final output. This triggers the `AgentCompleteEvent`.

### 6.11 LSP Custom Notifications

**Boundary**: Neovim client ↔ LSP server (JSON-RPC over stdio)

All custom notifications use the `$/remora/` prefix and are transported over the standard LSP JSON-RPC channel.

**`$/remora/cursorMoved`** (Client → Server):
```json
{"file_path": "/absolute/path/to/file.py", "line": 42, "character": 10}
```

**`$/remora/submitInput`** (Client → Server):
```json
// Chat message:
{"agent_id": "abc123def456789", "content": "Please add type hints"}
// Rejection feedback:
{"agent_id": "abc123def456789", "rejection_feedback": "Don't change the return type"}
```

**`$/remora/event`** (Server → Client):
```json
{
  "kind": "agent",
  "type": "AgentStartEvent",
  "graph_id": "swarm",
  "agent_id": "abc123def456789",
  "timestamp": 1234567890.123,
  "payload": {"node_name": "calculate_total", ...}
}
```

**`$/remora/agentsUpdated`** (Server → Client):
```json
{
  "agents": [
    {"node_id": "abc123", "name": "calculate_total", "status": "idle", "file_path": "..."},
    ...
  ]
}
```

**Gotchas**:
- These are **notifications**, not requests. There is no response expected.
- The Neovim plugin must register handlers for these methods. If not registered, the notifications are silently dropped by the LSP client.
- `$/remora/submitInput` with `rejection_feedback` triggers a new agent turn with the feedback included in the prompt. The agent sees what the user didn't like and can try again.

### 6.12 RemoraDB vs EventStore

**Why two databases?**

| Aspect | EventStore (`events.db`) | RemoraDB (`indexer.db`) |
|--------|--------------------------|-------------------------|
| **Scope** | Core system — all events and materialized node state | LSP-specific — editor integration data |
| **Tables** | `events`, `nodes` | `edges`, `proposals`, `cursor_focus`, `command_queue`, `activation_chain` |
| **Writer** | EventStore class (any mode) | RemoraDB class (LSP mode only) |
| **Shared across modes** | Yes — CLI, LSP, web service all read/write | No — only exists when LSP server runs |
| **Data lifecycle** | Append-only events + materialized views | Mutable state (proposals change status, commands are consumed) |
| **Read by Graph Viewer** | Yes (GraphState reads `nodes` table) | Partially (cursor_focus for highlighting) |

**The separation exists because**:
1. EventStore is the **source of truth** for the entire system. It's event-sourced and append-only. Any process can read it safely.
2. RemoraDB contains **transient, mutable state** specific to the editor integration. Proposals have status transitions. The command queue has items that are consumed and deleted. These don't belong in an append-only event log.
3. RemoraDB tables like `edges` (call graph) and `cursor_focus` are computed/transient data that can be rebuilt from the source code at any time. They don't need event-sourcing durability.

---

## 7. Shared State & SQLite Databases

A complete catalog of every SQLite database in the system.

### 7.1 events.db (EventStore)

**Location**: `{project_root}/.remora/events/events.db`

**Created by**: `EventStore.initialize()`

**Mode**: WAL

**Tables**:

```sql
-- Append-only event log
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,      -- JSON
    timestamp REAL NOT NULL,
    agent_id TEXT DEFAULT ''
);
CREATE INDEX idx_events_graph ON events(graph_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_agent ON events(agent_id);

-- Materialized node state (maintained by NodeProjection)
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT DEFAULT '',
    file_path TEXT NOT NULL,
    start_line INTEGER DEFAULT 0,
    end_line INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    language TEXT DEFAULT '',
    status TEXT DEFAULT 'idle',    -- idle, running, error, orphaned
    graph_id TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    bundle TEXT DEFAULT '',
    model TEXT DEFAULT '',
    system_prompt_override TEXT DEFAULT '',
    tool_filter TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',        -- JSON array
    metadata TEXT DEFAULT '{}',    -- JSON dict
    last_run REAL DEFAULT 0,
    run_count INTEGER DEFAULT 0,
    error_message TEXT DEFAULT ''
);
CREATE INDEX idx_nodes_file ON nodes(file_path);
CREATE INDEX idx_nodes_status ON nodes(status);
CREATE INDEX idx_nodes_graph ON nodes(graph_id);
```

**Access patterns**:
- **Write**: `EventStore.append()` — INSERTs events, UPSERTs/DELETEs nodes
- **Read**: `EventStore.replay()`, `get_recent_events()`, `list_nodes()`, `get_node()`
- **External readers**: GraphState (graph viewer), RemoraService (web dashboard)

### 7.2 subscriptions.db (SubscriptionRegistry)

**Location**: `{project_root}/.remora/subscriptions.db`

**Created by**: `SubscriptionRegistry.initialize()`

**Mode**: WAL

```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    event_types TEXT,    -- JSON array or NULL (match all)
    from_agents TEXT,    -- JSON array or NULL
    to_agent TEXT,       -- string or NULL
    path_glob TEXT,      -- glob pattern or NULL
    tags TEXT            -- JSON array or NULL
);
CREATE INDEX idx_subs_agent ON subscriptions(agent_id);
```

**Access patterns**:
- **Write**: `register()`, `unregister()`, `register_defaults()`
- **Read**: `get_matching_agents()` (but typically served from in-memory cache)
- **Cache**: On `initialize()`, all rows are loaded into memory. Mutations update both SQLite and the cache.

### 7.3 indexer.db (RemoraDB)

**Location**: `{project_root}/.remora/indexer.db`

**Created by**: `RemoraDB.__init__()`

**Mode**: WAL

```sql
CREATE TABLE edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,    -- "calls", "imports", "inherits"
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id, edge_type)
);

CREATE TABLE activation_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    parent_id TEXT,
    depth INTEGER NOT NULL,
    timestamp REAL NOT NULL
);

CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    original_source TEXT NOT NULL,
    proposed_source TEXT NOT NULL,
    diff TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',  -- pending, accepted, rejected
    created_at REAL NOT NULL
);

CREATE TABLE cursor_focus (
    id INTEGER PRIMARY KEY DEFAULT 1,  -- single row
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    character INTEGER NOT NULL,
    agent_id TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE command_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,
    payload TEXT NOT NULL,        -- JSON
    status TEXT DEFAULT 'pending',
    created_at REAL NOT NULL
);
```

**Access patterns**:
- **edges**: Written by ASTWatcher on file parse. Read by LazyGraph for topology.
- **proposals**: Written by AgentRunner on `rewrite_self`. Read/updated by LSP commands (accept/reject).
- **cursor_focus**: Written by `$/remora/cursorMoved` handler. Read by graph viewer.
- **command_queue**: Written by web frontend/CLI. Read/consumed by AgentRunner.poll_command_queue().
- **activation_chain**: Written by AgentRunner during cascade tracking. Read for debugging.

### 7.4 agents.db (SwarmState)

**Location**: `{project_root}/.remora/agents.db`

**Created by**: `SwarmState.__init__()`

**Mode**: WAL

```sql
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT DEFAULT '',
    file_path TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    bundle TEXT DEFAULT '',
    model TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

**Purpose**: Swarm-level agent registry, separate from EventStore's `nodes` table. Used by `SwarmExecutor` for quick agent lookups without going through event replay. Contains `AgentMetadata` dataclass instances.

**Access patterns**:
- `upsert(metadata)` — create or update agent entry
- `mark_orphaned(agent_id)` — set status to "orphaned"
- `list_agents()` — return all agents
- `get_agent(agent_id)` — return single agent

### 7.5 workspace.db / stable.db (Cairn)

**Location**: `{project_root}/.remora/workspaces/stable.db` and `{project_root}/.remora/workspaces/{agent_id}/workspace.db`

**Created by**: `CairnWorkspaceService.initialize()` and `get_agent_workspace()`

**Purpose**: Virtual filesystem for agent file operations.

- **`stable.db`** — the shared base workspace. Contains an index of all project files synced from disk. Incrementally updated via mtime tracking.
- **`workspace.db`** (per-agent) — copy-on-write fork of `stable.db`. Agent writes go here only. Provides isolation between agents.

**Access patterns**:
- `stable.db` is written during sync (on startup and file changes). Read by all agent workspaces as the CoW base.
- Per-agent `workspace.db` is written during agent tool execution (write_file). Read by the same agent's tools (read_file, list_dir, etc.).

---

## 8. Startup & Lifecycle

### 8.1 CLI Headless Mode

**Command**: `remora swarm start`

```
1. load_config(config_path)         → Config dataclass
2. Create infrastructure:
   - EventBus()
   - SubscriptionRegistry(subscriptions_path) → initialize()
   - NodeProjection()
   - EventStore(event_store_path, subscriptions, event_bus, projection) → initialize()
   - Wire: event_store.set_subscriptions(), event_store.set_event_bus()
3. reconcile_on_startup(root, subscriptions, event_store):
   - discover(paths) → all CSTNodes in the project
   - Diff against nodes table in EventStore
   - Emit NodeDiscoveredEvent for new/updated nodes
   - Emit NodeRemovedEvent for deleted nodes
   - Register default subscriptions for each agent
   - Emit ContentChangedEvent for changed nodes
   - Return {created, orphaned, total}
4. AgentRunner.create_headless(event_store, config params)
5. Start runner.run_forever() as asyncio task
6. Start runner.run_from_event_store(event_store) as asyncio task
7. Wait for Ctrl+C → runner.stop()
```

### 8.2 LSP Mode

**Command**: `remora swarm start --lsp`

```
Phase 1 — Preparation (synchronous, before LSP starts):
1. load_config()
2. Create EventBus, SubscriptionRegistry, NodeProjection, EventStore → initialize all
3. reconcile_on_startup() — same as headless mode

Phase 2 — LSP server startup:
1. Import lsp.__main__.main()
2. Pass event_store, subscriptions to LSP main
3. Inside LSP main:
   a. Create LLMClient (structured_agents)
   b. Create AgentRunner(event_store, subscriptions, llm_client, server_ref)
   c. Attach runner to server singleton
   d. Start LSP server (stdio transport, blocks on I/O)

Phase 3 — On INITIALIZED (LSP handshake complete):
1. Start runner.run_forever() as background asyncio task
2. Start _background_scan():
   - Walk entire workspace for source files
   - Parse each file with ASTWatcher
   - Emit NodeDiscoveredEvents
   - Update edges in RemoraDB
   - Inject IDs into source files
   - Refresh code lenses
3. Both tasks run concurrently with LSP request handling
```

### 8.3 Web Service Mode

**Command**: `remora serve`

```
1. load_config()
2. RemoraService.create_default(config, project_root):
   - Creates all core infrastructure (EventBus, EventStore, etc.)
   - Creates UiStateProjector
   - Subscribes projector to EventBus
3. create_app(service) → Starlette Application with routes
4. uvicorn.run(app, host, port)
```

**Note**: The web service does NOT run reconciliation or start an AgentRunner. It's a passive observer that reads from EventStore and streams UI updates. For agents to actually run, the LSP server or CLI swarm must be running in a separate process.

### 8.4 Graph Viewer Startup

**Location**: `remora-demo/frontend/graph/`

```
1. App factory: create_app(db_path, poll_interval)
2. Create GraphState(db_path) — opens events.db read-only
3. Create DBBridge(graph_state, relay, poll_interval)
4. Register Stario routes:
   - GET / → shell page (HTML with Datastar)
   - GET /subscribe → SSE stream via Writer
   - GET /graph → SVG rendering
   - GET /sidebar/{agent_id} → agent details
   - GET /events → event stream rendering
5. Start DBBridge polling loop as background task
6. Stario serves on configured host:port
```

**Note**: The Graph Viewer is completely independent of Remora's service layer. It connects directly to `events.db` via `GraphState`. It can run alongside the LSP server, the web service, or alone (showing the last known state from the database).
