# DEMO_ARCHITECTURE.md — Remora System Architecture

> Comprehensive architectural reference for the Remora agent system, covering the core engine, the Neovim demo (LSP integration), the Web demo (Stario + Datastar frontend), and the Graph Viewer. Particular attention is paid to **crossover interfaces** — the boundaries where data moves between systems, the shape of that data, and the constraints to be aware of.

---

## Table of Contents

1. [System Overview](#1-system-overview) — High-level diagram of the three major subsystems (Core, Neovim/LSP, Web/Service) and how they connect.

2. [Remora Core Architecture](#2-remora-core-architecture) — The engine that powers everything: events, discovery, agent model, subscriptions, projections, workspace, tools, and execution.
   - 2.1 [Event System](#21-event-system) — Frozen Pydantic event models, EventBus, EventStore (unified SQLite), routing fields.
   - 2.2 [Discovery Pipeline](#22-discovery-pipeline) — Tree-sitter based code parsing, CSTNode, node ID computation (`file_path:name:start_line:end_line`), `parse_file()`.
   - 2.3 [Agent Model (AgentNode)](#23-agent-model-agentnode) — Pydantic BaseModel that serves triple duty: DB row, LLM prompt, and LSP protocol response. Redesigned fields: source tracking, graph context, specialization.
   - 2.4 [AgentContext](#24-agentcontext) — Typed Pydantic model replacing the old `externals: dict`. Explicit callback fields for emit, subscribe, broadcast, query.
   - 2.5 [Subscriptions & Reactive Routing](#25-subscriptions--reactive-routing) — SubscriptionPattern (list fields), SubscriptionRegistry, shared connection mode, cache by event_type.
   - 2.6 [Projections](#26-projections) — NodeProjection: how the event log materializes into the `nodes` table.
   - 2.7 [Workspace & Cairn Integration](#27-workspace--cairn-integration) — AgentWorkspace, CairnBridge, CairnExternals, PathResolver, SyncMode, copy-on-write isolation.
   - 2.8 [Swarm Tools](#28-swarm-tools) — 5 structured tools (send_message, subscribe, unsubscribe, broadcast, query_agents) plus Grail tool discovery.
   - 2.9 [Kernel Factory](#29-kernel-factory) — `create_kernel()` shared factory deduplicating structured_agents setup.
   - 2.10 [Extensions](#210-extensions) — `extension_matches()`, backward-compat fallback, `.remora/models/` loading.
   - 2.11 [Configuration](#211-configuration) — `pydantic_settings.BaseSettings` with `REMORA_` env prefix, all field groups.
   - 2.12 [Error Hierarchy](#212-error-hierarchy) — RemoraError and its subclasses.

3. [The Data Flow Pipeline](#3-the-data-flow-pipeline) — End-to-end trace of how source code becomes agent activity.
   - 3.1 [Source Code to CSTNode](#31-source-code-to-cstnode) — File parsing, tree-sitter queries, node ID hashing, `start_byte`/`end_byte`.
   - 3.2 [CSTNode to EventStore](#32-cstnode-to-eventstore) — NodeDiscoveredEvent emission, JSON serialization, unified SQLite insertion.
   - 3.3 [EventStore to AgentNode](#33-eventstore-to-agentnode) — NodeProjection UPSERT, `nodes` table, `AgentNode.from_row()`.
   - 3.4 [Event to Trigger](#34-event-to-trigger) — SubscriptionRegistry matching, trigger queue (`asyncio.Queue`), cascade prevention (depth, cooldown, concurrency semaphore).
   - 3.5 [Trigger to Agent Turn](#35-trigger-to-agent-turn) — AgentRunner consuming the trigger, multi-round tool loop (max 5 rounds), system prompt building.

4. [Neovim Demo Architecture](#4-neovim-demo-architecture) — The LSP server that integrates Remora into Neovim as a language server.
   - 4.1 [LSP Server Structure](#41-lsp-server-structure) — RemoraLanguageServer, global singleton, handler registration, `emit_event()`, `notify_agents_updated()`.
   - 4.2 [AgentRunner](#42-agentrunner) — Unified async execution coordinator: trigger queue, cascade prevention, `execute_turn()`, multi-round tool loop, command queue polling, text-based tool call extraction for Qwen.
   - 4.3 [Unified SQLite Database](#43-unified-sqlite-database) — ALL tables in one DB, RemoraDB for LSP-specific access patterns (proposals, edges, activation_chain, cursor_focus, command_queue).
   - 4.4 [LazyGraph](#44-lazygraph) — Graph topology backed by rustworkx, lazy neighborhood loading, recursive CTE.
   - 4.5 [ASTWatcher](#45-astwatcher) — File parsing, ID injection (`# rm_xxxx`), node types (file/function/class/method), `source_code`/`source_hash`/`start_byte`/`end_byte`.
   - 4.6 [Proposals & Rewrites](#46-proposals--rewrites) — RewriteProposal model, `to_workspace_edit()`, `to_diagnostic()`, `to_code_actions()`.
   - 4.7 [LSP Handlers](#47-lsp-handlers) — Document lifecycle, hover, commands (getAgentPanel, chat, requestRewrite, executeTool, acceptProposal, rejectProposal, selectAgent, messageNode), code actions, code lens, document symbols.
   - 4.8 [Custom Notifications](#48-custom-notifications) — `$/remora/cursorMoved`, `$/remora/submitInput`, `$/remora/event`, `$/remora/agentsUpdated`.
   - 4.9 [Agent Tools in Neovim Context](#49-agent-tools-in-neovim-context) — `rewrite_self`, `message_node`, `read_node`.
   - 4.10 [Mock LLM Client](#410-mock-llm-client) — Script-based dispatch for deterministic demos, MockContext parsing, 6 golden path scripts.

5. [Web Demo Architecture](#5-web-demo-architecture) — The Stario + Datastar web frontend and its service layer.
   - 5.1 [Service Layer (RemoraService)](#51-service-layer-remoraservice) — Framework-agnostic API, `create_default()` factory, handler functions, event streaming.
   - 5.2 [Starlette Adapter](#52-starlette-adapter) — Route mapping, DatastarResponse, SSE streaming, swarm endpoints.
   - 5.3 [Datastar Integration](#53-datastar-integration) — `render_shell()`, `render_patch()`, `render_signals()`, SSE patch model.
   - 5.4 [UI Layer](#54-ui-layer) — UiStateProjector (event reduction), Component system (ABC, Element, layout/controls/data/dashboard), `render_dashboard()`.
   - 5.5 [ChatService](#55-chatservice) — Standalone Starlette chat app, `ChatSession` wrapping `AgentKernel`, session management, SSE event streaming.

6. [Graph Viewer Architecture](#6-graph-viewer-architecture) — The Stario-based real-time graph viewer (exists in two copies).
   - 6.1 [Two Copies, One Architecture](#61-two-copies-one-architecture) — `remora_demo/web/graph/` vs `frontend/graph/`, import path differences, column name differences.
   - 6.2 [GraphState](#62-graphstate) — Read-only WAL mode SQLite, `GraphSnapshot`, read methods, `push_command()` via separate writable connection.
   - 6.3 [DBBridge](#63-dbbridge) — Fingerprint-based polling, Relay publish, change detection (topology/status/cursor/events).
   - 6.4 [ForceLayout](#64-forcelayout) — Server-side force-directed simulation, repulsion/attraction/gravity/damping, hierarchy seeding.
   - 6.5 [Stario App Factory](#65-stario-app-factory) — Closure-based DI, routes (/, /subscribe, /agent/*, /events, /command), Datastar SSE updates.
   - 6.6 [SVG Rendering](#66-svg-rendering) — Catppuccin Mocha palette, node radius by type, status colors, edge styles, glow filter for focus.
   - 6.7 [Views](#67-views) — Shell (full HTML page), graph (SVG fragment), sidebar (tabbed detail panel), event stream (firehose).

7. [Crossover Interfaces](#7-crossover-interfaces) — Every boundary where data moves between subsystems.
   - 7.1 [Event Serialization Boundary](#71-event-serialization-boundary) — Pydantic event to JSON to SQLite and back.
   - 7.2 [EventStore to EventBus](#72-eventstore-to-eventbus) — In-process notification after persistence.
   - 7.3 [EventStore to SubscriptionRegistry to Trigger Queue](#73-eventstore-to-subscriptionregistry-to-trigger-queue) — Reactive routing within a single transaction.
   - 7.4 [AgentNode Triple Interface](#74-agentnode-triple-interface) — `to_row()`/`from_row()` (SQLite), `to_system_prompt()` (LLM), `to_code_lens()`/`to_hover()` (LSP).
   - 7.5 [Unified SQLite as Shared State Bus](#75-unified-sqlite-as-shared-state-bus) — How multiple processes share state through one SQLite DB in WAL mode.
   - 7.6 [command_queue Table](#76-command_queue-table) — Web frontend pushes commands, AgentRunner polls and dispatches.
   - 7.7 [cursor_focus Table](#77-cursor_focus-table) — Neovim cursor position to web graph highlight.
   - 7.8 [HTTP/SSE API Boundary](#78-httpsse-api-boundary) — Data shapes for all REST endpoints and SSE streams.
   - 7.9 [DBBridge Polling Loop](#79-dbbridge-polling-loop) — SQLite fingerprint polling, Relay publish, SSE to browser.
   - 7.10 [Cairn Externals Interface](#710-cairn-externals-interface) — How agent tools call through to the filesystem via PathResolver.
   - 7.11 [LSP Custom Notifications](#711-lsp-custom-notifications) — Data shapes for `$/remora/*` notifications between Neovim and the LSP server.
   - 7.12 [AgentContext Callback Boundary](#712-agentcontext-callback-boundary) — How tools call back into the system through typed AgentContext callbacks.

8. [Unified SQLite Database](#8-unified-sqlite-database) — The single database schema, all tables, access patterns.
   - 8.1 [events Table](#81-events-table) — Schema with routing fields (from_agent, to_agent, correlation_id, tags).
   - 8.2 [nodes Table](#82-nodes-table) — Redesigned schema with source tracking and graph context fields.
   - 8.3 [subscriptions Table](#83-subscriptions-table) — Subscription patterns, in-memory cache.
   - 8.4 [edges Table](#84-edges-table) — parent_of, calls edge types.
   - 8.5 [proposals Table](#85-proposals-table) — Rewrite proposals with status tracking.
   - 8.6 [cursor_focus Table](#86-cursor_focus-table) — Single-row table for current cursor position.
   - 8.7 [command_queue Table](#87-command_queue-table) — Command dispatch between web frontend and LSP runner.
   - 8.8 [activation_chain Table](#88-activation_chain-table) — Agent cascade tracking.

9. [Startup & Lifecycle](#9-startup--lifecycle) — How the system boots in each mode and what happens at each stage.
   - 9.1 [CLI Headless Mode](#91-cli-headless-mode) — `remora swarm start`: config load, reconciliation, `AgentRunner.create_headless()`, `run_forever()`.
   - 9.2 [LSP Mode](#92-lsp-mode) — `remora swarm start --lsp`: reconciliation, then LSP server with background scan and runner.
   - 9.3 [Web Service Mode](#93-web-service-mode) — `remora serve`: `RemoraService.create_default()`, Starlette app, uvicorn.
   - 9.4 [Graph Viewer Startup](#94-graph-viewer-startup) — Stario app factory, DBBridge initialization, `bridge.run()`, `app.serve()`.
   - 9.5 [Chat Service Mode](#95-chat-service-mode) — Standalone Starlette chat app, ChatSession lifecycle.

---

## 1. System Overview

Remora is an **event-sourced, reactive agent system** that treats every function, class, and file in a codebase as an autonomous agent. The system is built around a **single unified SQLite database** that serves as the shared state bus between all components.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REMORA CORE                                      │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  Discovery    │  │   Events     │  │ Subscriptions │  │  AgentNode   │  │
│  │  Pipeline     │  │  (Pydantic   │  │   Registry    │  │  (model +    │  │
│  │  (tree-sitter)│  │   frozen)    │  │  (shared conn)│  │   prompt)    │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  EventBus     │  │  EventStore  │  │ AgentContext  │  │ Kernel       │  │
│  │  (in-process) │  │  (unified    │  │ (typed Pydantic│ │ Factory      │  │
│  │               │  │   SQLite)    │  │  callbacks)   │  │              │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  Projections  │  │  Workspace   │  │  Extensions   │  │  Config      │  │
│  │  (nodes       │  │  + Cairn     │  │  (.remora/    │  │  (pydantic_  │  │
│  │   table)      │  │  Bridge      │  │   models/)    │  │   settings)  │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Swarm Tools (5 tools)                            │   │
│  │  send_message  subscribe  unsubscribe  broadcast  query_agents      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
        │                     │                               │
        │ SQLite WAL          │ SQLite WAL                    │ In-process
        │ (shared DB)         │ (shared DB)                   │ (imports)
        ▼                     ▼                               ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────────┐
│  NEOVIM DEMO    │   │  GRAPH VIEWER   │   │  WEB SERVICE DEMO           │
│  (LSP Server)   │   │  (Stario App)   │   │  (Starlette + Datastar)     │
│                 │   │                 │   │                             │
│  AgentRunner    │   │  GraphState     │   │  RemoraService              │
│  ASTWatcher     │   │  DBBridge       │   │  UiStateProjector           │
│  LazyGraph      │   │  ForceLayout    │   │  ChatService                │
│  RemoraDB       │   │  SVG Rendering  │   │  Component System           │
│  Proposals      │   │  Datastar SSE   │   │  Datastar SSE               │
│  Mock LLM       │   │                 │   │                             │
│                 │   │  Relay pub/sub  │   │  HTTP REST + SSE            │
│  LSP Protocol   │   │                 │   │                             │
└─────┬───────────┘   └────────┬────────┘   └────────────┬────────────────┘
      │                        │                          │
      │ LSP JSON-RPC           │ HTTP + SSE               │ HTTP + SSE
      │ + custom $/remora/*    │ (Stario)                 │ (Starlette)
      ▼                        ▼                          ▼
   Neovim Editor            Browser                    Browser / API Client
```

### Three Modes of Operation

The system runs in three distinct modes, all sharing the same unified SQLite database:

| Mode | Entry Point | Process Model | Primary Use |
|------|-------------|---------------|-------------|
| **LSP Mode** | `remora swarm start --lsp` | Single process: LSP server + AgentRunner + background scan | Neovim integration — the main demo |
| **CLI Headless** | `remora swarm start` | Single process: `AgentRunner.create_headless()` + `run_forever()` | Automated agent processing without an editor |
| **Web Service** | `remora serve` | Starlette ASGI app under uvicorn | Web dashboard with event streaming and agent control |

The **Graph Viewer** runs as a separate Stario process alongside any mode. It reads the shared SQLite database in WAL mode and pushes real-time SVG updates to the browser via Datastar SSE.

### Key Repositories

| Repository | Path | Contents |
|------------|------|----------|
| **Remora** (library) | `/remora/src/remora/` | Core engine, LSP server, service layer, UI system, CLI |
| **remora_demo** (in remora repo) | `/remora/remora_demo/` | Neovim demo: mock LLM, launch script, demo project, web graph viewer |
| **Frontend** (remora-demo repo) | `/remora-demo/frontend/` | Stario + Datastar graph viewer (copy), mock LLM, 179 tests |

### The Unified Database

The single most important architectural decision: **all state lives in one SQLite database** at `{project_root}/.remora/indexer.db`. This replaces the old multi-database architecture where events, subscriptions, agents, and LSP state lived in separate `.db` files. The unified database contains 8 tables:

- `events` — Append-only event log with routing fields
- `nodes` — Materialized agent state (via projections)
- `subscriptions` — Event routing patterns
- `edges` — Graph topology (parent_of, calls)
- `proposals` — Rewrite proposals with status tracking
- `cursor_focus` — Current cursor position (single-row)
- `command_queue` — Cross-process command dispatch
- `activation_chain` — Agent cascade tracking

All components share this database via SQLite WAL mode, enabling concurrent readers with a single writer.

## 2. Remora Core Architecture

The `remora.core` package (`/remora/src/remora/core/`) is the engine that powers all three modes of operation. It provides event sourcing, code discovery, agent modeling, reactive subscriptions, workspace isolation, and tool execution. Nothing in `core` depends on LSP, Starlette, or Stario — it is a pure library.

### 2.1 Event System

**Source:** `remora/core/events.py`

All Remora events are **frozen Pydantic `BaseModel` subclasses**. The base class `_FrozenEvent` sets `ConfigDict(frozen=True)`, making every event instance immutable and hashable.

Events fall into four categories:

| Category | Events | Purpose |
|----------|--------|---------|
| **Agent lifecycle** | `AgentStartEvent`, `AgentCompleteEvent`, `AgentErrorEvent` | Track execution status. Carry `graph_id`, `agent_id`. |
| **Human-in-the-loop** | `HumanInputRequestEvent`, `HumanInputResponseEvent` | Agent blocks waiting for human input; human responds. Linked by `request_id`. |
| **Reactive swarm** | `AgentMessageEvent`, `FileSavedEvent`, `ContentChangedEvent`, `ManualTriggerEvent` | Subscription-routed events. Carry routing fields: `from_agent`, `to_agent`, `tags`, `correlation_id`, `path`. |
| **Node lifecycle** | `NodeDiscoveredEvent`, `NodeRemovedEvent` | Emitted by discovery. Drive the `nodes` table projection. |

**Key event details:**

- `NodeDiscoveredEvent` carries `source_code`, `source_hash`, `start_byte`, `end_byte`, `parent_id` — everything needed to materialize a full `AgentNode` row.
- `ManualTriggerEvent` has `to_agent` for directed triggering.
- `AgentMessageEvent` has `from_agent`, `to_agent`, `tags` (tuple), and `correlation_id` for chain tracking.
- `FileSavedEvent` carries only `path` and `timestamp`.

**Re-exports:** The module re-exports 7 events from `structured_agents.events` (`KernelStartEvent`, `KernelEndEvent`, `ToolCallEvent`, `ToolResultEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `TurnCompleteEvent`). These are kernel-level execution events that flow through the same `EventBus`.

The union type `RemoraEvent` covers all 18 event types and is used for type annotations throughout the system.

### 2.2 Discovery Pipeline

**Source:** `remora/core/discovery.py`

Discovery converts source files into `CSTNode` objects using **tree-sitter** for language-aware parsing.

**CSTNode** is a frozen Pydantic `BaseModel` — immutable with `ConfigDict(frozen=True)`:

```python
class CSTNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str          # SHA256[:16] of "file_path:name:start_line:end_line"
    node_type: str        # "function", "class", "file", "section", "table"
    name: str             # e.g. "my_function"
    full_name: str        # e.g. "function:my_function"
    file_path: str
    text: str             # Full source code of the node
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int

    def __hash__(self) -> int:
        return hash(self.node_id)   # Identity by node_id only
```

**Custom `__hash__`**: Pydantic frozen models hash ALL fields by default, but CSTNode overrides `__hash__` to hash only by `node_id`. Two nodes with the same `node_id` but different `text` (e.g. after an edit) hash equally — this is intentional for set/dict operations during reconciliation diffs.

**Node ID computation** uses `compute_node_id(file_path, name, start_line, end_line)` — a SHA-256 of `"{file_path}:{name}:{start_line}:{end_line}"`, truncated to 16 hex characters. This is deterministic: identical code at the same position always produces the same ID. If code moves, the ID changes (by design — it's a new node).

**Parsing flow:**

1. `discover(paths, languages, node_types, max_workers)` is the public entry point.
2. It walks directories, detects language from extension (`LANGUAGE_EXTENSIONS` map: `.py` → `"python"`, `.ts` → `"typescript"`, etc.), and dispatches to a `ThreadPoolExecutor`.
3. Each file is parsed by `_parse_file(file_path, language)`:
   - Gets a tree-sitter `Parser` for the language via `_get_parser()`.
   - Reads file content and parses into a syntax tree.
   - Loads `.scm` query files from `remora/queries/{language}/remora_core/` via `_load_queries()`.
   - Runs query captures against the tree. Each capture becomes a `CSTNode`.
   - Always includes a file-level `CSTNode` with `node_type="file"`.
4. Results are sorted by `(file_path, start_line)`.

**Single-file convenience:** `parse_file(file_path)` parses one file and returns its `CSTNode` list. This is a standalone convenience function for ad-hoc parsing — note that the LSP server's `ASTWatcher` does **not** use this function; it has its own `_parse_file_only()` method with tree-sitter and regex fallback, plus incremental ID preservation logic.

### 2.3 Agent Model (AgentNode)

**Source:** `remora/core/agent_node.py`

`AgentNode` is a **Pydantic `BaseModel`** (mutable, not frozen) that serves triple duty:

1. **Database row** — `to_row()` / `from_row()` for SQLite serialization
2. **LLM prompt source** — `to_system_prompt()` generates the agent's identity prompt
3. **LSP protocol response** — `to_code_lens()`, `to_hover()`, `to_code_actions()`, `to_document_symbol()`

**Field groups:**

```
Identity (from CSTNode via projection):
  node_id, node_type, name, full_name, file_path,
  start_line, end_line, start_byte, end_byte,
  source_code, source_hash

Graph context (from edges table):
  parent_id, caller_ids: list[str], callee_ids: list[str]

Runtime state (from event projections):
  status: "idle" | "running" | "error" | "pending_approval"
  last_trigger_event, last_completed_at

Specialization (from extension config matching):
  extension_name, custom_system_prompt,
  mounted_workspaces: list[str],
  extra_tools: list[ToolSchema],
  extra_subscriptions: list[SubscriptionPattern]
```

**`ToolSchema`** is a Pydantic `BaseModel` co-located in the same module. It wraps a tool's `name`, `description`, and JSON Schema `parameters`, with converters `to_llm_tool()` (for LLM function calling) and `to_code_action()` (for LSP code actions).

**Serialization round-trip:** `to_row()` JSON-encodes list fields (`caller_ids`, `callee_ids`, `extra_tools`, `extra_subscriptions`, `mounted_workspaces`). `from_row()` parses them back, hydrating `ToolSchema` and `SubscriptionPattern` objects from the stored JSON.

**System prompt generation** (`to_system_prompt()`):

```
You are an autonomous AI agent embodying a {language} {node_type}: `{name}`

# Identity
- Node ID, location, parent

# Your Source Code
```{lang}
{source_code}
```

# Graph Context
- Called by: {caller_ids}
- You call: {callee_ids}

# Core Rules
1. You may ONLY edit your own body using `rewrite_self()`.
2. To request changes elsewhere, use `message_node(target_id, request)`.
3. All edits are proposals -- the human must approve before they apply.
```

If the node has `custom_system_prompt` (from extension matching), it appends a `# Specialization` section. If `mounted_workspaces` is non-empty, it appends an `# Available Workspaces` section.

**LSP helpers:** `to_code_lens()` renders a status icon (`●` idle, `▶` running, `⏸` pending_approval, `○` error) with the node ID. `to_hover()` shows a rich Markdown panel with ID, type, status, parent, callers, callees, extension, and recent events. `to_code_actions()` returns 3 built-in actions (chat, rewrite, message) plus any `extra_tools` as additional code actions. `to_document_symbol()` maps node types to LSP `SymbolKind` values.

### 2.4 AgentContext

**Source:** `remora/core/agent_context.py`

`AgentContext` is a **Pydantic `BaseModel`** (with `arbitrary_types_allowed=True`) that replaces the old `externals: dict[str, Any]` pattern. It carries typed callback fields:

```python
class AgentContext(BaseModel):
    agent_id: str
    correlation_id: str | None = None

    # Swarm callbacks (all async)
    emit_event: EmitEventFn         # (event_type: str, event: Any) -> None
    register_subscription: RegisterSubFn  # (agent_id: str, pattern: Any) -> None
    unsubscribe_subscription: UnsubscribeFn  # (sub_id: int) -> str
    broadcast: BroadcastFn          # (pattern: str, content: str) -> str
    query_agents: QueryAgentsFn     # (filter_type: str | None) -> list[Any]

    # Cairn file-system externals for Grail runtime
    cairn_externals: dict[str, Any] = {}
```

**`as_externals()`** merges `cairn_externals` (read_file, write_file, list_dir, etc.) with swarm callback keys into a flat dict. This is the backward-compatibility bridge for Grail scripts that expect `externals: dict[str, Any]`.

The `AgentContext` is constructed by the `SwarmExecutor` at turn start and passed to all swarm tools and Grail scripts. It is the single point where tools access the reactive system.

### 2.5 Subscriptions & Reactive Routing

**Source:** `remora/core/subscriptions.py`

The `SubscriptionRegistry` manages persistent event subscriptions in SQLite, enabling push-based event routing.

**`SubscriptionPattern`** is a Pydantic `BaseModel` with all-optional fields:

```python
class SubscriptionPattern(BaseModel):
    event_types: list[str] | None = None    # OR match (any of these types)
    from_agents: list[str] | None = None    # OR match (from any of these agents)
    to_agent: str | None = None             # Exact match (directed to this agent)
    path_glob: str | None = None            # PurePath.match() against event.path
    tags: list[str] | None = None           # Any tag overlap
```

A `None` field means "match anything". Multiple values in a list are OR-matched (any value matches). All non-None fields must match simultaneously (AND logic across fields).

**Two operating modes:**

| Mode | How | When |
|------|-----|------|
| **Shared** | Receives `connection` + `lock` from an `EventStore` | Normal operation — unified DB |
| **Standalone** | Opens its own SQLite connection from `db_path` | Backward compat, testing |

In shared mode, `initialize()` is a no-op (tables already created by `EventStore.initialize()`). In standalone mode, it creates the `subscriptions` table itself.

**In-memory cache:** The registry maintains a `dict[str, list[tuple[str, SubscriptionPattern]]]` indexed by `event_type`. When `get_matching_agents(event)` is called:

1. If cache is `None` (invalidated), rebuild from DB via `_rebuild_cache()`.
2. Look up candidates: `cache[event_type] + cache[""]` (where `""` holds wildcard subscriptions with no event_type filter).
3. Run `pattern.matches(event)` on each candidate, deduplicate by agent_id.

Cache is invalidated on any mutation (`register()`, `unregister()`, `unregister_all()`).

**Default subscriptions:** When a node is discovered, `register_defaults(agent_id, file_path)` creates two subscriptions:
- Direct message: `SubscriptionPattern(to_agent=agent_id)` — receives `AgentMessageEvent` and `ManualTriggerEvent` directed at this agent.
- Source file changes: `SubscriptionPattern(event_types=["ContentChangedEvent"], path_glob=file_path)` — triggers when the agent's source file is modified.

### 2.6 Projections

**Source:** `remora/core/projections.py`

`NodeProjection` materializes the event log into the `nodes` table. It processes events synchronously within the same SQLite transaction as the `EventStore.append()` call.

**Event handlers:**

| Event | Action |
|-------|--------|
| `NodeDiscoveredEvent` | **UPSERT** into `nodes`. Builds a full row with all fields. On conflict (same `node_id`), updates mutable fields but **preserves `status`**, `caller_ids`, `callee_ids`, and runtime state. |
| `NodeRemovedEvent` | **DELETE** from `nodes`. |
| `AgentStartEvent` | Sets `status = 'running'`, records `last_trigger_event`. |
| `AgentCompleteEvent` | Sets `status = 'idle'`, records `last_completed_at`. |
| `AgentErrorEvent` | Sets `status = 'error'`. |

**Extension matching during projection:** When a `NodeDiscoveredEvent` arrives, the projection iterates through `_extension_configs` (loaded from `.remora/models/`) and calls `extension_matches(ext, node_type, name, file_path, source_code)`. First match wins. The matched extension's `get_extension_data()` populates specialization fields (`extension_name`, `custom_system_prompt`, `mounted_workspaces`, `extra_tools`, `extra_subscriptions`).

### 2.7 Workspace & Cairn Integration

**Source:** `remora/core/workspace.py`, `remora/core/cairn_bridge.py`, `remora/core/cairn_externals.py`

Remora uses **Cairn** for copy-on-write workspace isolation. The architecture has three layers:

**`CairnWorkspaceService`** (`cairn_bridge.py`) — The top-level manager:
- Creates a **stable workspace** (`{swarm_root}/{graph_id}/stable.db`) that holds a snapshot of the project.
- Creates **per-agent workspaces** (`{swarm_root}/{graph_id}/agents/{agent_id[:2]}/{agent_id}/workspace.db`) with CoW isolation from stable.
- On `initialize(sync_mode=SyncMode.FULL)`, syncs all project files into the stable workspace (incremental by mtime).
- `get_externals(agent_id, agent_workspace)` builds a `CairnExternals` dict for Grail tool execution.
- Has a `PathResolver` instance for normalizing paths between project root and workspace.

**`AgentWorkspace`** (`workspace.py`) — Per-agent workspace wrapper:
- `read(path)` — Reads from agent workspace first, falls back to stable workspace, then optionally triggers `ensure_file_synced` for lazy loading.
- `write(path, content)` — Writes to agent workspace only (CoW isolated).
- `exists(path)`, `list_dir(path)` — Union of agent and stable workspace entries.
- All operations use `asyncio.Lock` for thread safety. Stable workspace uses a separate shared lock.

**`CairnExternals`** (`cairn_externals.py`) — Grail external function bridge:
- Wraps `CairnExternalFunctions` from the Cairn runtime.
- Normalizes all paths through `PathResolver.to_workspace_path()` before delegation.
- Provides: `read_file`, `write_file`, `list_dir`, `file_exists`, `search_files`, `search_content`, `submit_result`, `log`.
- `as_externals()` returns a flat dict for Grail script execution.

**`CairnDataProvider`** (`workspace.py`) — Loads files for Grail virtual FS:
- `load_files(node, related)` reads the agent's source file and any related files from the workspace.
- Falls back to direct disk reads if workspace misses.
- Used by `RemoraGrailTool` to populate the Grail virtual filesystem.

**`SyncMode`** enum: `FULL` (sync all project files) or `NONE` (skip sync).

### 2.8 Swarm Tools

**Source:** `remora/core/tools/swarm.py`, `remora/core/tools/grail.py`

Agents have access to 5 structured tools for swarm communication, plus dynamically discovered Grail tools.

**Swarm Tools** (all extend `SwarmTool` base class):

| Tool | Parameters | Behavior |
|------|-----------|----------|
| `send_message` | `to_agent: str`, `content: str` | Creates and emits an `AgentMessageEvent` via `ctx.emit_event`. |
| `subscribe` | `event_types: list[str]`, `from_agents: list[str]`, `path_glob: str` | Registers a new `SubscriptionPattern` via `ctx.register_subscription`. |
| `unsubscribe` | `subscription_id: int` | Removes a subscription via `ctx.unsubscribe_subscription`. |
| `broadcast` | `to_pattern: str`, `content: str` | Broadcasts to a pattern (`"children"`, `"siblings"`, `"file:/path"`) via `ctx.broadcast`. |
| `query_agents` | `filter_type: str` (optional) | Lists agents in the swarm, optionally filtered by node type, via `ctx.query_agents`. |

Each tool produces a `ToolResult` (from `structured_agents.types`) with `call_id`, `name`, `output`, and `is_error`. All tools are built via `build_swarm_tools(ctx: AgentContext)`.

**Grail Tool Discovery** (`grail.py`):

`discover_grail_tools(agents_dir, context, files_provider)` scans a directory for `.pym` files and creates `RemoraGrailTool` instances:
- Each `.pym` file is loaded via `grail.load()`.
- Parameters are derived from the script's `Input()` declarations via `_build_parameters()`.
- At execution time, the tool calls `files_provider()` to populate a virtual FS, filters externals to only those the script declares, and runs the script.
- Swarm tools are appended after Grail tools.

### 2.9 Kernel Factory

**Source:** `remora/core/kernel_factory.py`

`create_kernel()` is a shared factory that deduplicates the boilerplate for creating an `AgentKernel` from `structured_agents`:

```python
def create_kernel(
    *,
    model_name: str,      # e.g. "Qwen/Qwen3-4B"
    base_url: str,        # OpenAI-compatible API URL
    api_key: str,         # API key ("EMPTY" for local)
    timeout: float = 300.0,
    tools: list[Any] | None = None,
    observer: Any | None = None,
    grammar_config: Any | None = None,
    client: Any | None = None,
) -> AgentKernel:
```

It builds an OpenAI-compatible client via `build_client()`, creates a `ModelAdapter` with the appropriate response parser for the model, optionally attaches a `ConstraintPipeline` for grammar-constrained decoding, and returns a configured `AgentKernel`.

Used by both `SwarmExecutor._run_kernel()` and `ChatSession.send()`.

### 2.10 Extensions

**Source:** `remora/extensions.py`

Extensions customize agent behavior via Python classes in `.remora/models/`. They follow a convention-over-configuration pattern.

**`AgentExtension`** base class has two static methods:
- `matches(node_type, name, *, file_path="", source_code="")` — Returns `True` if this extension applies.
- `get_extension_data()` — Returns a dict of `AgentNode` field overrides (e.g. `custom_system_prompt`, `mounted_workspaces`, `extra_tools`).

**`extension_matches()`** calls `ext.matches()` with the widened 4-param API, falling back to the old 2-param `(node_type, name)` signature with a warning for backward compatibility.

**`load_extensions(models_dir)`** scans `.remora/models/*.py` for `AgentExtension` subclasses:
- Files are loaded in alphabetical order (so `00_specific.py` before `50_generic.py`).
- **Mtime-based caching** at module level — skips reload if no file timestamps changed.
- Returns a list of extension classes for `NodeProjection` to use during event processing.

### 2.11 Configuration

**Source:** `remora/core/config.py`

`Config` is a `pydantic_settings.BaseSettings` subclass with `env_prefix="REMORA_"`, so every field can be overridden via `REMORA_` environment variables.

**Field groups:**

| Group | Fields | Defaults |
|-------|--------|----------|
| **Discovery** | `project_path`, `discovery_paths`, `discovery_languages`, `discovery_max_workers` | `"."`, `("src/",)`, `None`, `4` |
| **Bundles** | `bundle_root`, `bundle_mapping`, `bundle_mapping_tools` | `"agents"`, `{}`, `{}` |
| **Model** | `model_base_url`, `model_default`, `model_api_key` | `"http://localhost:8000/v1"`, `"Qwen/Qwen3-4B"`, `""` |
| **Swarm** | `swarm_root`, `swarm_id`, `max_concurrency`, `max_turns`, `truncation_limit`, `timeout_s`, `max_trigger_depth`, `trigger_cooldown_ms`, `chat_history_limit` | `".remora"`, `"swarm"`, `4`, `8`, `1024`, `300.0`, `5`, `1000`, `5` |
| **Workspace** | `workspace_ignore_patterns`, `workspace_ignore_dotfiles` | Standard ignores (`.git`, `.venv`, etc.), `True` |
| **Neovim** | `nvim_enabled`, `nvim_socket` | `False`, `".remora/nvim.sock"` |

**Loading:** `load_config(path)` reads from a `remora.yaml` file. If `path` is None, it searches upward from CWD, stopping at the nearest `pyproject.toml`. Falls back to defaults if no file is found.

### 2.12 Error Hierarchy

**Source:** `remora/core/errors.py`

All Remora-specific errors inherit from `RemoraError`:

```
RemoraError
├── ConfigError        — Configuration loading or validation
├── DiscoveryError     — Code discovery failures
├── GraphError         — Graph construction or validation
├── ExecutionError     — Agent execution failures
├── WorkspaceError     — Workspace operations
└── SwarmError         — Swarm operations
```

These are used throughout the codebase for structured error handling. External consumers can catch `RemoraError` to handle all Remora-specific failures.

---

### 2.S EventBus and EventStore

Two additional core components that bridge events to consumers:

**EventBus** (`remora/core/event_bus.py`) — In-process event dispatch implementing the `structured_agents` Observer protocol:
- `emit(event)` dispatches to type-matched handlers and wildcard (`subscribe_all`) handlers.
- `subscribe(event_type, handler)` / `subscribe_all(handler)` for registration.
- `stream(*event_types)` returns an async context manager yielding an `AsyncIterator` of events (backed by `asyncio.Queue`).
- `wait_for(event_type, predicate, timeout)` blocks until a matching event arrives.
- `clear()` removes all handlers (both type-specific and wildcard). Used for cleanup in tests and session teardown.
- Error policy: `"log"` (default, swallows errors with warning) or `"propagate"` (re-raises).

**EventStore** (`remora/core/event_store.py`) — The unified SQLite persistence layer:
- `initialize()` creates ALL 8 tables (events, nodes, subscriptions, edges, activation_chain, proposals, cursor_focus, command_queue) with WAL mode enabled.
- `append(graph_id, event)` is the central write path:
  1. Serializes event to JSON (Pydantic `model_dump()`, dataclass `asdict()`, or `vars()` fallback).
  2. Inserts into `events` table with routing fields (`from_agent`, `to_agent`, `correlation_id`, `tags`).
  3. Applies `NodeProjection` within the **same transaction** as the INSERT.
  4. Commits.
  5. Post-commit: queries `SubscriptionRegistry.get_matching_agents()` and pushes `(agent_id, event_id, event)` tuples to the trigger queue.
  6. Emits to `EventBus` for in-process consumers.
- `get_triggers()` is an async iterator that yields from the trigger queue — consumed by `AgentRunner`.
- `replay(graph_id, event_types, since, until, after_id)` replays events with filtering.
- Node queries: `get_node()`, `list_nodes()`, `get_node_at_position()`, `set_node_status()`, `remove_nodes_for_file()`.
- The `connection` and `lock` are shared with `SubscriptionRegistry` (shared mode) and `RemoraDB` (LSP-specific access patterns).

## 3. The Data Flow Pipeline

This section traces a single piece of source code from disk to agent execution, step by step.

### 3.1 Source Code to CSTNode

**Entry points:** `discover()` (bulk scan) or `parse_file()` (single file, used by ASTWatcher).

1. A Python file at `/project/src/utils.py` is read from disk.
2. Language detected from `.py` extension → `"python"`.
3. `_get_parser("python")` loads `tree_sitter_python.language()` into a `tree_sitter.Parser`.
4. The file content is parsed into a syntax tree.
5. `.scm` queries from `remora/queries/python/remora_core/` are loaded and run against the tree.
6. Each query capture becomes a `CSTNode`:
   - The capture name prefix determines `node_type` (e.g. `"function"`, `"class"`).
   - `_extract_name()` pulls the function/class name from a `.name` capture or common child node types.
   - `compute_node_id("src/utils.py", "my_func", 10, 25)` → SHA-256 of `"src/utils.py:my_func:10:25"` → `"a3f8c1d2e4b5..."` (16 hex chars).
   - `start_byte`/`end_byte` come directly from the tree-sitter node.
   - `text` is extracted via byte slicing: `content[node.start_byte:node.end_byte]`.
7. A file-level `CSTNode` (type `"file"`) is always included.

### 3.2 CSTNode to EventStore

**Happens during:** Reconciliation (`reconcile_on_startup()`) or incremental parsing (ASTWatcher).

1. Each `CSTNode` is converted to a `NodeDiscoveredEvent`:
   ```python
   NodeDiscoveredEvent(
       node_id=cst_node.node_id,
       node_type=cst_node.node_type,
       name=cst_node.name,
       full_name=cst_node.full_name,
       file_path=cst_node.file_path,
       start_line=cst_node.start_line,
       end_line=cst_node.end_line,
       start_byte=cst_node.start_byte,
       end_byte=cst_node.end_byte,
       source_code=cst_node.text,
       source_hash=sha256(cst_node.text)[:16],
       parent_id=None,   # Set later by reconciler or watcher
   )
   ```
2. The event is passed to `EventStore.append(swarm_id, event)`.
3. Inside `append()`:
   - Event serialized to JSON via Pydantic `model_dump()`.
   - Inserted into `events` table with routing fields (`from_agent`, `to_agent`, etc.).
   - `NodeProjection.apply()` runs in the **same transaction**.
   - Transaction committed.

### 3.3 EventStore to AgentNode

**Happens inside:** `NodeProjection._project_node_discovered()`.

1. The projection builds a full row dict from the event fields.
2. Extension configs are checked: `extension_matches(ext, node_type, name, file_path, source_code)`. First match populates `extension_name`, `custom_system_prompt`, `mounted_workspaces`, `extra_tools`, `extra_subscriptions`.
3. The row is UPSERT'd into the `nodes` table:
   - On INSERT: full row with `status = "idle"`.
   - On CONFLICT (same `node_id`): updates identity/source/extension fields but **preserves runtime state** (`status`, `caller_ids`, `callee_ids`, `last_trigger_event`, `last_completed_at`).
4. To read back as an `AgentNode`: `AgentNode.from_row(row)` parses JSON fields (`caller_ids`, `callee_ids`, `extra_tools`, `extra_subscriptions`, `mounted_workspaces`).

### 3.4 Event to Trigger

**Happens after:** `EventStore.append()` commits.

1. Post-commit, `append()` calls `SubscriptionRegistry.get_matching_agents(event)`.
2. The registry checks its in-memory cache:
   - Looks up `cache[event_type]` (e.g. `cache["ContentChangedEvent"]`) for type-specific subscriptions.
   - Also checks `cache[""]` for wildcard subscriptions.
   - For each candidate `(agent_id, pattern)`, calls `pattern.matches(event)` — checks `event_types`, `from_agents`, `to_agent`, `path_glob`, `tags`.
3. Each matching `agent_id` gets a tuple `(agent_id, event_id, event)` pushed to the `trigger_queue` (`asyncio.Queue`).

**Cascade prevention** (handled by `AgentRunner`, see Section 4.2):
- `max_trigger_depth` (default 5) — prevents infinite event chains.
- `trigger_cooldown_ms` (default 1000ms) — debounces rapid re-triggers.
- `max_concurrency` semaphore (default 4) — limits parallel agent runs.

### 3.5 Trigger to Agent Turn

**Happens in:** `SwarmExecutor.run_agent(node, trigger_event)` or `AgentRunner.execute_turn()`.

1. `AgentRunner` (or headless runner) consumes `(agent_id, event_id, event)` from the trigger queue.
2. Loads `AgentNode` from the `nodes` table via `EventStore.get_node(agent_id)`.
3. Emits `AgentStartEvent` → projection sets `status = "running"`.
4. `SwarmExecutor.run_agent()` executes:
   a. Resolves the bundle path from `config.bundle_mapping[node.node_type]`.
   b. Loads the structured-agents manifest.
   c. Initializes workspace (Cairn stable + per-agent CoW workspace).
   d. Builds `AgentContext` with callbacks wired to EventStore, SubscriptionRegistry, and node queries.
   e. Loads files via `CairnDataProvider`.
   f. Retrieves chat history from `EventStore.get_recent_events()`.
   g. Builds the user prompt: target identity, source code (from workspace), trigger event info, chat history.
   h. Discovers tools: Grail `.pym` scripts + 5 swarm tools.
   i. Creates an `AgentKernel` via `create_kernel()` (reusing the pooled LLM client).
   j. Runs `kernel.run(messages, tool_schemas, max_turns)` — multi-round tool loop.
5. On success: emits `AgentCompleteEvent` → projection sets `status = "idle"`, `last_completed_at`.
6. On error: emits `AgentErrorEvent` → projection sets `status = "error"`.
7. Any events emitted by tools (e.g. `AgentMessageEvent` from `send_message`) re-enter the pipeline at step 3.4, potentially triggering other agents.

**Reconciliation at startup** (`reconcile_on_startup()`):

Before the trigger loop starts, reconciliation diffs discovered `CSTNode`s against the existing `nodes` table:
- **New nodes:** emit `NodeDiscoveredEvent` + register default subscriptions.
- **Deleted nodes:** emit `NodeRemovedEvent` + unregister all subscriptions.
- **Changed nodes** (different `source_hash`): re-emit `NodeDiscoveredEvent` (updates the row) + emit `ContentChangedEvent` (may trigger subscribed agents).

Returns a summary: `{created, orphaned, updated, total}`.

## 4. Neovim Demo Architecture

The Neovim demo integrates Remora into Neovim as a **Language Server Protocol (LSP)** server. Every code function, class, and file becomes an agent visible through code lenses, hover info, diagnostics, and custom commands. The LSP server uses **pygls** (Python Generic Language Server) as its protocol layer and connects to a real or mock LLM for agent turns.

**Package:** `remora.lsp` — `server.py`, `runner.py`, `db.py`, `graph.py`, `watcher.py`, `models.py`, `notifications.py`, `handlers/` (6 modules).

### 4.1 LSP Server Structure

**File:** `remora/src/remora/lsp/server.py`

`RemoraLanguageServer` extends pygls `LanguageServer` and serves as the central hub:

```python
class RemoraLanguageServer(LanguageServer):
    def __init__(self, event_store=None, subscriptions=None):
        super().__init__(name="remora", version="0.1.0")
        self.db = RemoraDB()                    # LSP-specific DB (proposals, edges, etc.)
        self.event_store = event_store           # Core EventStore (shared)
        self.graph = LazyGraph(self.db, ...)     # rustworkx-backed graph topology
        self.watcher = ASTWatcher()              # Tree-sitter based file parser
        self.proposals: dict[str, RewriteProposal] = {}  # In-memory proposal cache
        self.runner: AgentRunner | None = None   # Attached after initialization
        self._injecting: set[str] = set()        # URIs being ID-injected (skip re-parse)
        self.subscriptions = subscriptions       # Core SubscriptionRegistry
```

**Key design patterns:**

1. **Global singleton** — `server = get_server()` at module level, `atexit.register(server.shutdown)`. Handler decorators reference this singleton at import time.

2. **Handler registration** — `register_handlers()` force-imports all handler modules (`actions`, `capabilities`, `commands`, `documents`, `hover`, `lens`) plus `notifications`. Each module uses `@server.feature()` or `@server.command()` decorators to register.

3. **`emit_event(event)`** — Central event emission: sets timestamp, appends to EventStore, then notifies the Neovim client via `$/remora/event` custom notification. Every handler calls this through the module-level `emit_event()` function.

4. **`notify_agents_updated()`** — Queries `event_store.list_nodes()` and sends `$/remora/agentsUpdated` with all active agents to the Neovim client (for sidebar updates).

5. **`discover_tools_for_agent(agent)`** — Loads Grail tools from the agent's bundle directory (via `config.bundle_mapping[agent.node_type]`), returning `list[ToolSchema]`.

6. **Correlation IDs** — `generate_correlation_id()` produces `corr_{counter}_{uuid_hex[:8]}` for tracing cascading agent activations.

7. **Shutdown** — Cleanly closes `RemoraDB` and `LazyGraph` connections.

### 4.2 AgentRunner

**File:** `remora/src/remora/lsp/runner.py`

The `AgentRunner` is the **unified asynchronous execution coordinator** that works identically for both LSP and CLI/headless mode. It merges the LSP-specific tool loop with core cascade safety features.

**Architecture:**

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  trigger()           │ ──▶ │  asyncio.Queue    │ ──▶ │ execute_turn │
│  (cooldown + depth) │     │  (Trigger items) │     │ (semaphore)  │
└─────────────────────┘     └──────────────────┘     └──────┬───────┘
                                                            │
                                                    ┌───────▼───────┐
                                                    │  LLM chat()   │
                                                    │  ◀─ tool loop ▶│
                                                    │  (max 5 rounds)│
                                                    └───────────────┘
```

**Constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_CHAIN_DEPTH` | 10 | Max cascade depth (DB-backed + in-memory) |
| `MAX_TOOL_ROUNDS` | 5 | Max LLM ↔ tool round-trips per turn |

**Trigger model:**

```python
class Trigger(BaseModel):
    agent_id: str
    correlation_id: str
    context: dict = {}  # e.g. {"rejection_feedback": "..."}
```

**`trigger(agent_id, correlation_id, context=None)`** — Entry point for scheduling agent execution:

1. **Cooldown check** (`_check_cooldown`) — In-memory, per-agent, `trigger_cooldown_ms` (default 1000ms).
2. **In-memory depth check** (`_check_depth_limit`) — Tracks `{agent_id}:{correlation_id}` → `(depth, timestamp)`.
3. **DB-backed chain check** — `RemoraDB.get_activation_chain(correlation_id)` returns ordered list of agent_ids. Rejects if `len(chain) >= MAX_CHAIN_DEPTH` or if `agent_id` already in chain (cycle detection).
4. Enqueues `Trigger` to `asyncio.Queue`.

**`execute_turn(trigger)`** — The core execution method:

1. Increments correlation depth tracking.
2. Acquires concurrency semaphore (`max_concurrency=4`).
3. Sets node status to `"running"` via EventStore.
4. Records agent in activation chain via `RemoraDB.add_to_chain()`.
5. Loads `AgentNode` from EventStore.
6. Applies extensions via `apply_extensions()` (loads `.remora/models/`, pattern-matches on node_type/name/file_path/source_code).
7. Builds message list:
   - System message: `agent.to_system_prompt()`
   - User messages: from `event_store.get_events_for_correlation()` — `HumanChatEvent` and `AgentMessageEvent` targeting this agent
   - Rejection feedback context (if present)
8. Gets tool schemas via `get_agent_tools(agent)`.
9. **Multi-round tool loop** (up to `MAX_TOOL_ROUNDS`):
   - Calls `llm.chat(messages, tools)` → `LLMResponse`
   - Calls `handle_response(agent, response, correlation_id)` → `list[dict]` of tool results
   - If no tool results → turn complete (text-only response or side-effect-only tools)
   - If tool results → appends assistant message + tool results as user messages, continues loop
10. On error: emits `AgentErrorEvent`.
11. Finally: decrements depth tracking, sets status to `"idle"`, refreshes code lenses.

**`handle_response(agent, response, correlation_id)`** — Processes an LLM response:

- **Text-based tool call extraction** (`_extract_text_tool_calls`): For models like Qwen that emit `<tool_call>{"name": ..., "arguments": ...}</tool_call>` as text rather than structured tool_calls.
- **Text-only response**: Emits `AgentEvent(event_type="AgentTextResponse")`.
- **Tool calls dispatched by name** (match/case):

| Tool | Action | Returns result? |
|------|--------|----------------|
| `rewrite_self` | `create_proposal(agent, new_source, correlation_id)` | No (side-effect) |
| `message_node` | Resolves symbolic targets (`"parent"` → `agent.parent_id`), calls `message_node()` | No (side-effect) |
| `read_node` | Loads target from EventStore, returns JSON `{name, type, source, file}` | Yes |
| `*` (other) | `execute_extension_tool()` → emits `ToolResultEvent` | No |

**Headless mode** — `AgentRunner.create_headless(event_store, llm)`:

Creates a `_HeadlessServer` adapter (duck-type compatible with `RemoraLanguageServer`) wrapping `_HeadlessDB` stubs. All DB operations become no-ops. The runner operates identically without any editor connection.

**`run_forever()`** — Main event loop:
1. Starts `poll_command_queue()` as a background task.
2. Loops: dequeues triggers, calls `execute_turn()`.

**`run_from_event_store(event_store)`** — Bridge for CLI mode: async-iterates `event_store.get_triggers()` and enqueues them.

### 4.3 Unified SQLite Database

**File:** `remora/src/remora/lsp/db.py`

`RemoraDB` handles LSP-specific operational state that doesn't belong in the event-sourced core. It operates in **two modes**:

| Mode | Trigger | Tables |
|------|---------|--------|
| **Standalone** | `RemoraDB(db_path=...)` | Opens own connection, creates schema |
| **Shared** | `RemoraDB(connection=..., lock=...)` | Reuses EventStore's connection, assumes tables exist |

In shared mode, `EventStore.initialize()` has already created all tables (events, nodes, edges, activation_chain, proposals, cursor_focus, command_queue). RemoraDB simply operates against the shared connection.

**Tables managed by RemoraDB** (created in standalone mode):

```sql
-- Agent hierarchy and call graph
CREATE TABLE edges (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,  -- 'parent_of' | 'calls'
    PRIMARY KEY (from_id, to_id, edge_type)
);

-- Cascade depth tracking per correlation
CREATE TABLE activation_chain (
    correlation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    depth INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    PRIMARY KEY (correlation_id, agent_id)
);

-- Rewrite proposals pending human approval
CREATE TABLE proposals (
    proposal_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    old_source TEXT NOT NULL,
    new_source TEXT NOT NULL,
    diff TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending' | 'accepted' | 'rejected'
    created_at REAL NOT NULL,
    file_path TEXT
);

-- Single-row cursor position for web graph highlighting
CREATE TABLE cursor_focus (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    agent_id TEXT,
    file_path TEXT,
    line INTEGER,
    timestamp REAL
);

-- Inter-process command queue (web → LSP runner)
CREATE TABLE command_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,
    agent_id TEXT,
    payload JSON NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at REAL NOT NULL,
    processed_at REAL
);
```

**Thread safety:** All mutating methods use the `@async_db` decorator which wraps the sync DB call in `asyncio.to_thread()` with a threading lock. Read methods (`get_cursor_focus`, `poll_commands`, `mark_command_done`) are synchronous for direct use from web server polling.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `update_cursor_focus(agent_id, file_path, line)` | Upsert cursor position (from `$/remora/cursorMoved`) |
| `get_cursor_focus()` | Read cursor (for graph viewer highlight) |
| `add_to_chain(correlation_id, agent_id)` | Track cascade depth |
| `get_activation_chain(correlation_id)` | List agents in cascade |
| `update_edges(nodes)` | Rebuild `parent_of` and `calls` edges from parsed nodes |
| `store_proposal(...)` | Persist rewrite proposal |
| `get_proposals_for_file(file_path)` | Load pending proposals for diagnostics |
| `push_command(command_type, agent_id, payload)` | Enqueue command from web frontend |
| `poll_commands(limit)` | Dequeue pending commands (FIFO) |
| `mark_command_done(command_id)` | Mark command as processed |

**Connection lifecycle:** In standalone mode, `close()` closes the SQLite connection. In shared mode, `close()` is a no-op (the EventStore owns the connection).

### 4.4 LazyGraph

**File:** `remora/src/remora/lsp/graph.py`

`LazyGraph` provides **graph topology** backed by rustworkx (`rx.PyDiGraph`), loading neighborhoods on demand rather than the full graph. It uses **two separate SQLite connections**: one for edges (from RemoraDB) and one for nodes (from EventStore).

```python
class LazyGraph:
    def __init__(self, db: RemoraDB, event_store_db_path: str | None = None):
        self._edges_conn = sqlite3.connect(str(db.db_path), ...)  # RemoraDB for edges
        self._nodes_conn = sqlite3.connect(event_store_db_path, ...)  # EventStore for nodes
        self.graph = rx.PyDiGraph()
        self.node_indices: dict[str, int] = {}  # node_id → rustworkx index
        self.loaded_files: set[str] = set()      # files whose nodes are loaded
```

**Key operations:**

- **`ensure_loaded(node_id)`** — If node isn't in the graph, loads its 2-hop neighborhood:
  1. Queries edges with a **recursive CTE** to find all nodes within `depth=2` hops.
  2. Fetches node data from EventStore's `nodes` table.
  3. Adds nodes and edges to the rustworkx graph.

- **`invalidate(file_path)`** — Removes all nodes for a file from the in-memory graph (called on `did_save`).

- **`get_parent(node_id)`** — Walks predecessors looking for `parent_of` edges.

- **`get_callers(node_id)`** — Walks predecessors looking for `calls` edges.

- **`_normalize_node(row)`** — Ensures both `id` and `node_id` keys exist (compatibility across EventStore column naming).

**Graceful degradation:** If `rustworkx` is not installed, `RUSTWORKX_AVAILABLE = False` and all graph operations return empty results.

### 4.5 ASTWatcher

**File:** `remora/src/remora/lsp/watcher.py`

`ASTWatcher` parses source files into agent nodes using **tree-sitter** (with a regex fallback). It handles the initial discovery of what code entities exist in a file.

**Supported file types:**

| Suffix | Parsing | Nodes produced |
|--------|---------|----------------|
| `.py` | Tree-sitter (full AST) | `file` + `function` + `class` + `method` |
| `.md`, `.toml` | File-level only | `file` |
| Other | Not parsed | (empty) |

**`parse_and_inject_ids(uri, text, old_nodes)`** — Main entry point:

1. Determines file suffix → routes to `_find_definitions()` (Python), `_parse_file_only()` (non-Python), or `_parse_fallback()` (no tree-sitter).
2. Always creates a **file-level node** first: `node_type="file"`, `name=stem`, `source_code=text[:200]`, `source_hash=md5(text)`.
3. For Python files, recursively walks the tree-sitter AST looking for `function_definition` and `class_definition` nodes.

**Node ID stability:** The watcher preserves IDs across re-parses by matching `(name, node_type)` against `old_nodes`. If a match is found, the existing `node_id` is reused. New nodes get `rm_{random8}` IDs via `generate_id()`.

**Node fields produced:**

| Field | Source |
|-------|--------|
| `node_id` | Preserved from old or `generate_id()` |
| `node_type` | `"file"`, `"function"`, `"class"`, `"method"` |
| `name` | Tree-sitter name node text |
| `full_name` | `"{parent_full_name}.{name}"` (dot-separated hierarchy) |
| `file_path` | URI as passed (not converted) |
| `start_line`, `end_line` | 1-based line numbers from tree-sitter |
| `start_byte`, `end_byte` | Byte offsets from tree-sitter |
| `source_code` | Full source text of the node |
| `source_hash` | `md5(source_code)` |
| `parent_id` | Enclosing class or file node ID |

**Method vs. function detection:** A `function_definition` is classified as `"method"` if its parent chain is `function_def → block → class_definition`.

**`inject_ids(file_path, nodes)`** — Post-parse step that writes `# rm_xxxxxxxx` comment tags into the actual source file at each definition line. Processes nodes in reverse line order to preserve line numbers. Strips old `# rm_*` tags before adding new ones.

**Fallback parser** (`_parse_fallback`): Uses regex `^(\s*)(def|class)\s+(\w+)` when tree-sitter is unavailable. Produces approximate ranges (start_byte/end_byte = 0, end_line = total_lines).

### 4.6 Proposals & Rewrites

**File:** `remora/src/remora/lsp/models.py`

`RewriteProposal` is a Pydantic model representing an agent's proposed code change, bridging three LSP concepts:

```python
class RewriteProposal(BaseModel):
    proposal_id: str
    agent_id: str
    file_path: str
    old_source: str
    new_source: str
    start_line: int
    end_line: int
    reasoning: str = ""
    correlation_id: str = ""

    @computed_field
    @property
    def diff(self) -> str: ...  # unified_diff of old → new
```

**Triple interface:**

| Method | LSP concept | Purpose |
|--------|-------------|---------|
| `to_workspace_edit()` | `WorkspaceEdit` | Applies the rewrite to the file via `workspace/applyEdit` |
| `to_diagnostic()` | `Diagnostic` | Shows the proposal as an informational diagnostic at the function location |
| `to_code_actions()` | `list[CodeAction]` | Returns "✅ Accept rewrite" and "❌ Reject with feedback" quick-fix actions |

**Proposal lifecycle:**

1. Agent calls `rewrite_self` tool → `AgentRunner.create_proposal()`:
   - Creates `RewriteProposal` model
   - Stores in `server.proposals` dict (in-memory)
   - Sets node status to `"pending_approval"` in EventStore
   - Persists to `proposals` table via `RemoraDB.store_proposal()`
   - Publishes diagnostics to Neovim
   - Emits `RewriteProposalEvent`
2. User sees diagnostic in editor → triggers code action
3. **Accept** (`remora.acceptProposal`): applies `WorkspaceEdit`, deletes from proposals dict, updates DB status to `"accepted"`, resets node to `"idle"`, emits `RewriteAppliedEvent`
4. **Reject** (`remora.rejectProposal`): prompts for feedback via `$/remora/requestInput`, emits `RewriteRejectedEvent`, re-triggers the agent with `context={"rejection_feedback": feedback}`

### 4.7 LSP Handlers

**Directory:** `remora/src/remora/lsp/handlers/`

Six handler modules register on the global `server` singleton:

#### `documents.py` — Document lifecycle

**`did_open`** (`textDocument/didOpen`):
1. Gets existing nodes from EventStore for the file.
2. Parses file via `watcher.parse_and_inject_ids(uri, text, old_dicts)`.
3. Emits `NodeDiscoveredEvent` for each parsed node → EventStore projection upserts.
4. Updates edges in RemoraDB via `db.update_edges(new_dicts)`.
5. Refreshes code lenses.
6. Loads pending proposals for the file → publishes diagnostics.
7. Discovers Grail tools for each agent.
8. Sends `$/remora/agentsUpdated` notification.

**`did_save`** (`textDocument/didSave`):
1. Skips if URI is in `_injecting` set (was just ID-injected, avoid re-parse loop).
2. Re-parses the file, detecting orphaned nodes (old IDs not in new parse).
3. Emits `NodeRemovedEvent` for orphans, `NodeDiscoveredEvent` for current nodes.
4. Updates edges, invalidates LazyGraph cache.
5. **Injects `# rm_xxxxxxxx` ID tags** into the source file for Python files.
6. Refreshes code lenses and sends agents-updated notification.

**`did_close`** (`textDocument/didClose`):
- Removes proposals for the closed file from the in-memory cache.

#### `hover.py` — Hover information

**`hover`** (`textDocument/hover`):
- Queries `event_store.get_node_at_position(uri, line)`.
- Loads 5 recent events for the agent.
- Returns `agent.to_hover(events)` — a Markdown-formatted hover card showing agent identity, status, and recent activity.

#### `commands.py` — Editor commands

Eight commands registered via `@server.command()`:

| Command | Trigger | Action |
|---------|---------|--------|
| `remora.getAgentPanel` | Panel request | Returns `{agent, tools, events}` dict for the agent at cursor |
| `remora.chat` | User chat | Resolves agent at cursor, sends `$/remora/requestInput` prompt |
| `remora.requestRewrite` | Rewrite request | Like chat but with "What should this code do?" prompt |
| `remora.executeTool` | Direct tool call | Calls `runner.execute_extension_tool()` |
| `remora.acceptProposal` | Accept action | Applies workspace edit, updates status, emits event |
| `remora.rejectProposal` | Reject action | Sends `$/remora/requestInput` for feedback |
| `remora.selectAgent` | Agent selection | Sends `$/remora/agentSelected` notification |
| `remora.messageNode` | Message agent | Sends `$/remora/requestInput` prompt for message |

**Agent resolution** (`_resolve_agent`): Takes `{uri, line}` cursor context from args, queries `event_store.get_node_at_position()`, returns `agent_id` or shows a warning if no agent found.

#### `actions.py` — Code actions

**`code_action`** (`textDocument/codeAction`):
- Finds agent at the cursor position.
- Returns `agent.to_code_actions()` (standard agent actions) plus any pending proposal actions.

#### `lens.py` — Code lens and document symbols

**`code_lens`** (`textDocument/codeLens`):
- Lists all agents for the file via `event_store.list_nodes(file_path=uri)`.
- Returns `agent.to_code_lens()` for each — an inline indicator above each function/class.

**`document_symbol`** (`textDocument/documentSymbol`):
- Same query, returns `agent.to_document_symbol()` for each — Neovim outline integration.

#### `capabilities.py` — Initialization

**`on_initialize`** (`initialize`):
- Logs connection. Command capabilities are auto-registered by pygls 2.x decorators.

### 4.8 Custom Notifications

**File:** `remora/src/remora/lsp/notifications.py`

Two custom notification handlers registered on the server:

#### `$/remora/cursorMoved`

Sent by the Neovim client when the cursor moves. Params: `{uri, line}`.

Handler:
1. Normalizes params (pygls may deliver attrs objects instead of dicts).
2. Queries `event_store.get_node_at_position(uri, line)` to find the agent under the cursor.
3. Updates `cursor_focus` table via `db.update_cursor_focus(agent_id, uri, line)`.

This is the bridge between Neovim cursor position and web graph viewer highlighting.

#### `$/remora/submitInput`

Sent by the Neovim client when the user submits text from a `$/remora/requestInput` prompt. Params contain either `{agent_id, input}` or `{proposal_id, input}`.

**Chat path** (`agent_id` present):
1. Emits `HumanChatEvent` targeting the agent.
2. Triggers the runner for the agent.

**Rejection path** (`proposal_id` present):
1. Emits `RewriteRejectedEvent` with feedback.
2. Re-triggers the agent with `context={"rejection_feedback": feedback}`.

#### Other notifications (outbound, server → client)

| Notification | Direction | Payload |
|--------------|-----------|---------|
| `$/remora/event` | Server → Client | `event.model_dump()` — every event as it's emitted |
| `$/remora/agentsUpdated` | Server → Client | `[{node_id, name, status, node_type, file_path, parent_id}, ...]` |
| `$/remora/requestInput` | Server → Client | `{agent_id, prompt}` or `{proposal_id, prompt}` |
| `$/remora/agentSelected` | Server → Client | `{agent_id}` |

### 4.9 Agent Tools in Neovim Context

The LSP runner provides **3 built-in tools** plus extension tools to every agent:

#### `rewrite_self`

**Parameters:** `{new_source: str}`

Creates a `RewriteProposal` — the agent proposes a change to its own source code. The human must accept or reject it via code actions. This is **not** an auto-apply; it's a proposal-based flow.

**Side effects:** Creates proposal in DB, sets status to `"pending_approval"`, publishes diagnostic, emits `RewriteProposalEvent`. Does **not** return a tool result (side-effect only).

#### `message_node`

**Parameters:** `{target_id: str, message: str}`

Sends a message to another agent. Supports symbolic target `"parent"` which resolves to `agent.parent_id`.

**Side effects:** Emits `AgentMessageEvent` (from_agent → to_agent), then calls `runner.trigger(to_id, correlation_id)` to activate the target agent. Side-effect only.

#### `read_node`

**Parameters:** `{target_id: str}`

Reads another agent's current source code. Returns JSON `{name, type, source, file}`. Supports symbolic `"parent"` resolution. This is the **only built-in tool that returns data** to the LLM for the next round.

#### Extension tools

`agent.extra_tools` (list of `ToolSchema`) are appended to the tool list via `tool.to_llm_tool()`. Unknown tool calls are dispatched to `execute_extension_tool()`, which emits a `ToolResultEvent`.

### 4.10 Mock LLM Client

**File:** `remora/remora_demo/neovim/mock_llm.py`

`MockLLMClient` provides **deterministic, scripted responses** for the demo, conforming to the same `chat()` interface as the real `LLMClient`.

**Architecture:**

```
messages ──▶ parse_context() ──▶ MockContext ──▶ scripts[].matches() ──▶ respond()
```

#### MockContext

Parsed from the message list:

| Field | Extracted from |
|-------|---------------|
| `agent_name` | System prompt: `"agent for \`{name}\`"` |
| `agent_type` | System prompt: `"node_type: function"` etc. |
| `extension_name` | System prompt: `"TestFunction"` or `"PackageInit"` keywords |
| `trigger_type` | Last user message prefix pattern |
| `trigger_message` | Full text of last user message |
| `from_agent` | `"[From {agent}]"` prefix extraction |
| `round_number` | Count of assistant messages in the conversation |
| `system_prompt` | Full system prompt text |

**Trigger type detection** (from last user message):

| Pattern | Trigger type |
|---------|-------------|
| `"[From {agent}]: ..."` | `"agent_message"` |
| `"[Feedback on rejected proposal]: ..."` | `"rejection"` |
| `"[Tool result for ..."` | `"tool_followup"` |
| Contains "changed"/"parameter"/"added" | `"content_changed"` |
| Default | `"human_chat"` |

#### Script System

`Script` is an ABC with `matches(ctx) -> bool` and `respond(ctx) -> LLMResponse`. First match wins.

**6 golden path scripts** (in priority order):

| Script | Matches when | Response |
|--------|-------------|----------|
| `TestAgentUpdateScript` | `extension_name == "TestFunction"` + `trigger_type == "agent_message"` | Round 0: `read_node("load_config")`. Round 1+: `rewrite_self(updated_test)` |
| `TestAgentToolFollowupScript` | `extension_name == "TestFunction"` + `trigger_type == "tool_followup"` + round > 0 | `rewrite_self(updated_test)` |
| `ContentChangedAnalyzeScript` | Non-test function + `trigger_type == "content_changed"` + round 0 | Analyzes change, `message_node("test_load_yaml", ...)` |
| `RejectionFeedbackScript` | `trigger_type == "rejection"` | Text-only acknowledgment of feedback |
| `GenericToolFollowupScript` | `trigger_type == "tool_followup"` + round > 0 | Text-only "everything consistent" |
| `HumanChatScript` | `trigger_type == "human_chat"` + round 0 | Per-agent description (hardcoded for `load_config`, `detect_format`, `validate`, `deep_merge`) |

**Golden path demo flow:**

1. User edits `load_config` → adds `timeout` parameter
2. `did_save` → `ContentChangedEvent` triggers `load_config` agent
3. `ContentChangedAnalyzeScript` fires → agent calls `message_node("test_load_yaml", "update for timeout...")`
4. `AgentMessageEvent` triggers `test_load_yaml` agent
5. `TestAgentUpdateScript` round 0 → agent calls `read_node("load_config")`
6. Tool result feeds back → `TestAgentUpdateScript` round 1 → agent calls `rewrite_self(updated_test_code)`
7. Proposal appears as diagnostic in Neovim → user accepts/rejects

**`MockLLMClient`:**

```python
class MockLLMClient:
    def __init__(self, scripts: list[Script] | None = None):
        self.scripts = scripts or default_scripts()
        self.call_count = 0

    async def chat(self, messages, tools=None) -> LLMResponse:
        self.call_count += 1
        ctx = parse_context(messages)
        for script in self.scripts:
            if script.matches(ctx):
                return script.respond(ctx)
        return LLMResponse(content=f"Acknowledged. I'm {ctx.agent_name}, monitoring for changes.", tool_calls=[])
```

Tracks `call_count` for test assertions. Falls back to a generic acknowledgment if no script matches.

## 5. Web Demo Architecture

The web demo provides a **Starlette + Datastar** frontend for Remora's service layer. It renders a live dashboard showing agent activity, event streams, and interactive controls — all updated in real-time via Server-Sent Events (SSE). A separate `ChatService` provides a standalone chat interface backed by `AgentKernel`.

**Packages:** `remora.service` (api, handlers, datastar, chat_service), `remora.adapters.starlette`, `remora.ui` (projector, view, components).

### 5.1 Service Layer (RemoraService)

**File:** `remora/src/remora/service/api.py`

`RemoraService` is a **framework-agnostic** API layer that encapsulates all Remora functionality. It doesn't depend on Starlette — the adapter layer connects it to HTTP.

**`create_default()` factory:**

```python
@classmethod
def create_default(cls, *, config=None, config_path=None, project_root=None, enable_event_store=True):
    resolved_config = config or load_config(config_path)
    resolved_root = normalize_path(project_root or Path.cwd()).resolve()
    event_bus = EventBus()
    subscriptions = SubscriptionRegistry(swarm_root / "subscriptions.db")
    event_store = EventStore(store_path, subscriptions=subscriptions, projection=NodeProjection())
    workspace_service = CairnWorkspaceService(config, swarm_root, project_root)
    return cls(config=..., project_root=..., event_bus=..., ...)
```

Creates all dependencies: `EventBus`, `EventStore` (with `NodeProjection`), `SubscriptionRegistry`, `CairnWorkspaceService`. The projector subscribes to all events: `event_bus.subscribe_all(projector.record)`.

**`ServiceDeps` dataclass:**

```python
@dataclass(slots=True)
class ServiceDeps:
    event_bus: EventBus
    config: Config
    project_root: Path
    projector: UiStateProjector
    event_store: EventStore | None
    subscriptions: SubscriptionRegistry | None
    workspace_service: CairnWorkspaceService | None
```

Passed to all handler functions — pure dependency injection, no global state.

**Key methods:**

| Method | Returns | Purpose |
|--------|---------|---------|
| `index_html()` | `str` | Full HTML page: `render_shell(render_dashboard(state))` |
| `subscribe_stream()` | `AsyncIterator[str]` | SSE stream: yields initial patch + subsequent patches on every event |
| `events_stream()` | `AsyncIterator[str]` | Raw SSE event stream: `event: {type}\ndata: {json}\n\n` |
| `replay_events(graph_id, ...)` | `AsyncIterator[dict]` | Replays persisted events from EventStore |
| `input(request_id, response)` | `InputResponse` | Handles human input for blocked agents |
| `emit_event(event_type, data)` | `dict` | Emits `AgentMessageEvent` or `ContentChangedEvent` |
| `list_agents()` | `list[dict]` | Lists all agents via EventStore |
| `get_agent(agent_id)` | `dict` | Gets single agent via EventStore |
| `get_agent_subscriptions(agent_id)` | `list[dict]` | Gets subscriptions for an agent |

**Handler functions** (`remora/src/remora/service/handlers.py`):

| Handler | Purpose |
|---------|---------|
| `handle_input` | Emits `HumanInputResponseEvent` to unblock an agent |
| `handle_config_snapshot` | Returns `ConfigSnapshot.from_config(config)` |
| `handle_ui_snapshot` | Returns `projector.snapshot()` |
| `handle_swarm_emit` | Constructs typed event from `event_type` + `data`, appends to EventStore |
| `handle_swarm_list_agents` | `event_store.list_nodes()` → `[agent.model_dump()]` |
| `handle_swarm_get_agent` | `event_store.get_node(id)` → `agent.model_dump()` |
| `handle_swarm_get_subscriptions` | `subscriptions.get_subscriptions(id)` → pattern dicts |

### 5.2 Starlette Adapter

**File:** `remora/src/remora/adapters/starlette.py`

`create_app(service)` creates a `Starlette` application with closure-based route handlers that delegate to `RemoraService`:

| Route | Method | Handler | Response type |
|-------|--------|---------|---------------|
| `/` | GET | `index` | `HTMLResponse` — full dashboard page |
| `/subscribe` | GET | `subscribe` | `DatastarResponse` — SSE patches for live updates |
| `/events` | GET | `events` | `StreamingResponse` (SSE) — raw event stream |
| `/replay` | GET | `replay` | `StreamingResponse` (SSE) — event replay with optional follow mode |
| `/input` | POST | `submit_input` | `JSONResponse` — human input submission |
| `/config` | GET | `config` | `JSONResponse` — config snapshot |
| `/snapshot` | GET | `snapshot` | `JSONResponse` — UI state snapshot |
| `/swarm/agents` | GET | `swarm_agents` | `JSONResponse` — agent list |
| `/swarm/agents/{id}` | GET | `swarm_agent` | `JSONResponse` — single agent |
| `/swarm/events` | POST | `swarm_events` | `JSONResponse` — emit event |
| `/swarm/subscriptions/{id}` | GET | `swarm_subscriptions` | `JSONResponse` — agent subscriptions |

**SSE helper** (`_sse_response`): Sets `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no` headers for proper SSE streaming through proxies.

**Replay endpoint** supports `follow=true` mode: after replaying historical events, continues polling every 500ms for new events (like `tail -f`).

### 5.3 Datastar Integration

**File:** `remora/src/remora/service/datastar.py`

Three rendering functions bridge the UI layer to Datastar's SSE patch protocol:

| Function | Purpose |
|----------|---------|
| `render_shell(body, *, title, init_path)` | Full HTML page with Datastar JS, inline CSS, `data-on-load="@get('/subscribe')"` on `<body>` |
| `render_patch(state, *, bundle_default)` | `SSE.patch_elements(render_dashboard(state))` — sends HTML fragment as Datastar element patch |
| `render_signals(signals)` | `SSE.patch_signals(signals)` — sends signal updates |

**Datastar flow:**

1. Browser loads `GET /` → receives full HTML shell with `data-on-load="@get('/subscribe')"`.
2. Datastar client opens SSE connection to `/subscribe`.
3. Server yields initial HTML patch (full dashboard), then on every EventBus event yields an updated patch.
4. Datastar morphs the DOM — elements with matching `id` attributes are updated in place.

**CSS:** Inline in the shell — system-ui font, card layout, grid-based 2-column main panel, responsive at 768px breakpoint. Agent states get color-coded indicators (green=started, blue=completed, red=failed, gray=skipped).

### 5.4 UI Layer

**Files:** `remora/src/remora/ui/projector.py`, `remora/src/remora/ui/view.py`, `remora/src/remora/ui/components/`

#### UiStateProjector

An in-memory event reducer that maintains a JSON-serializable UI state:

```python
@dataclass(slots=True)
class UiStateProjector:
    events: deque[dict]       # Last 200 events (normalized envelopes)
    blocked: dict[str, dict]  # request_id → {agent_id, question, options}
    agent_states: dict[str, dict]  # agent_id → {state, name}
    results: list[dict]       # Last 50 agent completion results
    total_agents: int
    completed_agents: int
    failed_agents: int
    recent_targets: deque[str]  # Last 10 graph launch targets
```

**`record(event)`** — Processes each event and updates state:
- `AgentStartEvent` → adds to `agent_states` with `state="started"`, increments `total_agents`
- `HumanInputRequestEvent` → adds to `blocked`
- `HumanInputResponseEvent` → removes from `blocked`
- `AgentCompleteEvent` → sets `state="completed"`, increments `completed_agents`, adds to `results`
- `AgentErrorEvent` → sets `state="failed"`, increments both `completed_agents` and `failed_agents`

**`normalize_event(event)`** — Wraps any event into a UI envelope: `{kind, type, graph_id, agent_id, timestamp, payload}`. `EventKind` enum: `graph`, `agent`, `human`, `tool`, `model`, `kernel`, `turn`, `event`.

**`snapshot()`** — Returns the full state dict for rendering.

#### Component System

**Base classes** (`components/base.py`):

| Class | Purpose |
|-------|---------|
| `Component` (ABC) | `render() -> str`, `__str__` delegates to render, `__add__` creates `ComponentGroup` |
| `ComponentGroup` | Renders children sequentially |
| `RawHTML` | Passes content through without HTML escaping |
| `Element` | Generic HTML element: `tag`, `content`, `id`, `class_`, `attrs`, `data_attrs`, `self_closing` |

**Component modules:**

| Module | Components |
|--------|-----------|
| `layout.py` | `Card`, `Container`, `FlexRow`, `Grid`, `Panel` |
| `controls.py` | `Button`, `Input`, `Select` |
| `data.py` | `List`, `ListItem`, `ProgressBar`, `StatusBadge` |
| `dashboard.py` | `AgentStatusList`, `BlockedAgentCard`, `EventsList`, `GraphLauncher`, `ResultsList` |

#### `render_dashboard(state, *, bundle_default)` 

Composes the full dashboard from state:

```
<main id="remora-root">
  <div class="header">  ──  "Remora Dashboard" + agent count
  <div class="main">     ──  2-column grid:
    <div id="events-panel">  ──  EventsList
    <div id="main-panel">    ──  GraphLauncher + BlockedAgents + AgentStatus + Results + ProgressBar
```

Each component has a stable `id` attribute so Datastar can morph updates efficiently.

### 5.5 ChatService

**File:** `remora/src/remora/service/chat_service.py`

A standalone Starlette app for interactive chat backed by `ChatSession` (which wraps `AgentKernel`).

**Architecture:**

```
Browser ──REST──▶ Starlette ──▶ ChatSession ──▶ AgentKernel ──▶ LLM
   ▲                                  │
   └──SSE── EventBus ◀── ToolCallEvent/ToolResultEvent ◀──┘
```

**`ChatServiceState`** — Module-level singleton holding:
- `sessions: dict[str, ChatSession]` — active sessions
- `event_buses: dict[str, EventBus]` — per-session event buses

**Routes:**

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/sessions` | POST | `create_session` | Creates `ChatSession` from `ChatConfig` |
| `/sessions/{id}` | DELETE | `delete_session` | Closes session, cleans up |
| `/sessions/{id}/messages` | POST | `send_message` | Sends message, returns response + turn_count |
| `/sessions/{id}/history` | GET | `get_history` | Returns full conversation history |
| `/sessions/{id}/events` | GET | `stream_events` | SSE stream of `ToolCallEvent` / `ToolResultEvent` |
| `/tools` | GET | `list_tools` | Lists available tool presets |
| `/health` | GET | `health` | Health check + session count |

**`ChatConfig`** fields: `workspace_path`, `system_prompt`, `tool_presets` (default `["file_ops"]`), `model_name` (default `"Qwen/Qwen3-4B"`).

**Default tool names:** `read_file`, `write_file`, `list_dir`, `file_exists`, `search_files`, `discover_symbols`.

**Session lifecycle:**
1. `POST /sessions` → validates workspace path, creates `EventBus`, creates `ChatSession.create(config, event_bus)`.
2. `POST /sessions/{id}/messages` → `session.send(content)` → returns `{message: {id, role, content, timestamp, tool_calls}, turn_count}`.
3. `GET /sessions/{id}/events` → SSE stream: `event: tool_call\ndata: {name, arguments, timestamp}` and `event: tool_result\ndata: {name, output, is_error, timestamp}`.
4. `DELETE /sessions/{id}` → `session.close()`, cleanup.

**App factory** — `create_app(state=None)` accepts injectable state or falls back to the module singleton. Logs cairn availability on startup.

## 6. Graph Viewer Architecture

The graph viewer is a **Stario + Datastar** web application that provides real-time visualization of the agent graph. It reads the shared SQLite database (in WAL mode) written by the LSP server or headless runner, renders a server-side force-directed SVG layout, and pushes DOM patches to the browser via SSE. The viewer is **read-only** with respect to the main database tables — it only writes to the `command_queue` table to send commands back to the LSP server.

Two nearly identical copies of the graph viewer exist in separate repositories, targeting different DB schemas.

### 6.1 Two Copies, One Architecture

| Property | Frontend copy | remora_demo copy |
|----------|---------------|------------------|
| **Location** | `remora-demo/frontend/graph/` | `remora/remora_demo/web/graph/` |
| **Import prefix** | `graph.*` | `remora_demo.web.graph.*` |
| **Test suite** | 179 tests in `frontend/tests/` | None (manual testing) |
| **Python requirement** | 3.14 (Stario requires it) | 3.14 (same) |

The two copies share identical architecture, identical SVG rendering, identical CSS, identical layout engine, and identical bridge logic. The differences are confined to the **data layer** (`state.py` and `bridge.py`), where column name assumptions differ between the two DB schemas:

**Column name differences in `state.py`:**

| Operation | Frontend (`node_id` schema) | remora_demo (`id` schema) |
|-----------|-----------------------------|---------------------------|
| Snapshot normalization | `if "node_id" in n: n["remora_id"] = n.pop("node_id")` | `if "id" in n: n["remora_id"] = n.pop("id")` |
| Single node query | `WHERE node_id = ?` | `WHERE id = ?` |
| Events query columns | `id as event_id, from_agent, to_agent` | `event_id, agent_id` |
| Events filter | `WHERE from_agent = ? OR to_agent = ?` | `WHERE agent_id = ? OR json_extract(payload, '$.to_agent') = ?` |
| Recent events columns | `id as event_id, from_agent, to_agent` | `event_id, agent_id` |

**Fingerprint query difference in `bridge.py`:**

| Fingerprint | Frontend | remora_demo |
|-------------|----------|-------------|
| Node status ordering | `ORDER BY node_id` | `ORDER BY id` |

Both copies normalize the primary key column to `remora_id` in the returned dicts, so all downstream code (layout, SVG rendering, views) works identically regardless of which copy is running.

### 6.2 GraphState

**Files:** `frontend/graph/state.py`, `remora_demo/web/graph/state.py`

`GraphState` is the read-only data layer — it opens the shared SQLite database in WAL mode with `PRAGMA query_only=ON` and provides snapshot reads.

**Connection setup:**

```python
class GraphState:
    def __init__(self, db_path: str = ".remora/indexer.db") -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA query_only=ON")
        self._conn.row_factory = sqlite3.Row
        return self._conn
```

Key design: `query_only=ON` prevents accidental writes. `check_same_thread=False` allows the bridge to call from `asyncio.to_thread`. `Row` factory enables dict-style access.

**`GraphSnapshot` dataclass:**

```python
@dataclass
class GraphSnapshot:
    nodes: list[dict]         # All non-orphaned nodes
    edges: list[dict]         # All edges (parent_of, calls)
    cursor_focus: dict | None # {agent_id, file_path, line, timestamp} or None
    timestamp: float          # Read time
```

**Read methods:**

| Method | Query | Returns |
|--------|-------|---------|
| `read_snapshot()` | `SELECT * FROM nodes WHERE status != 'orphaned'` + all edges + cursor_focus | `GraphSnapshot` |
| `read_node(node_id)` | `SELECT * FROM nodes WHERE node_id = ?` | `dict \| None` |
| `read_events_for_agent(agent_id, limit=20)` | Events where `from_agent` or `to_agent` matches | `list[dict]` |
| `read_proposals_for_agent(agent_id)` | `SELECT * FROM proposals WHERE agent_id = ? AND status = 'pending'` | `list[dict]` |
| `read_edges_for_node(node_id)` | 4 queries for parents/children/callers/callees | `dict` with 4 lists |
| `read_recent_events(limit=30)` | Most recent events with `json_extract` for message/content | `list[dict]` |

**`push_command()` — the write exception:**

The graph viewer is read-only *except* for `push_command()`, which inserts into `command_queue`. This uses a **separate writable connection** (not the read-only one) that is opened, used, and immediately closed:

```python
def push_command(self, command_type: str, agent_id: str | None, payload: dict) -> int:
    conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO command_queue (command_type, agent_id, payload, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (command_type, agent_id, json.dumps(payload), time.time()),
    )
    conn.commit()
    cmd_id = cursor.lastrowid
    conn.close()
    return cmd_id
```

This is the **command channel** from the web UI back to the LSP server — the `AgentRunner` polls `command_queue` and dispatches commands (chat messages, approve/reject proposals, etc.).

### 6.3 DBBridge

**Files:** `frontend/graph/bridge.py`, `remora_demo/web/graph/bridge.py`

`DBBridge` is the polling loop that detects database changes and publishes notifications to the Stario `Relay`. SSE handlers subscribe to Relay subjects and push DOM patches to the browser.

**Architecture:**

```
SQLite DB ──poll──▶ DBBridge ──publish──▶ Relay ──subscribe──▶ SSE handler ──patch──▶ Browser
```

**`RelayProtocol`** — A `typing.Protocol` with a single method `publish(subject: str, data: str) -> None`. This abstraction allows testing without Stario installed — tests provide a mock relay.

**Constructor:**

```python
class DBBridge:
    def __init__(self, state: GraphState, layout: ForceLayout, relay: RelayProtocol,
                 poll_interval: float = 0.3) -> None:
```

**Fingerprint-based change detection:**

Instead of watching for filesystem events or querying every row, the bridge reads lightweight "fingerprints" — `count(*), max(rowid)` for each table. When a fingerprint changes between polls, that table has been modified.

| Fingerprint key | Query | Detects |
|----------------|-------|---------|
| `nodes` | `SELECT count(*), max(rowid) FROM nodes` | Node added/removed |
| `node_status` | `SELECT group_concat(status) FROM (SELECT status FROM nodes WHERE status != 'orphaned' ORDER BY node_id)` | Status change without topology change |
| `edges` | `SELECT count(*), max(rowid) FROM edges` | Edge added/removed |
| `cursor` | `SELECT timestamp FROM cursor_focus WHERE id = 1` | Cursor moved |
| `events` | `SELECT max(rowid) FROM events` | New event appended |

**Published subjects:**

| Subject | Triggered by | Effect in SSE handler |
|---------|-------------|----------------------|
| `graph.topology` | nodes or edges fingerprint changed | Re-read snapshot, re-render SVG |
| `graph.status` | node_status fingerprint changed | Re-read snapshot, re-render SVG |
| `graph.cursor` | cursor fingerprint changed | Re-read snapshot, re-render SVG |
| `graph.events` | events fingerprint changed | Re-read recent events, re-render event list |

**Topology change handling:** When `graph.topology` fires, the bridge also updates the layout engine — it calls `layout.set_graph()` with the new nodes and edges, then `layout.step(50)` for incremental settling. This ensures that when the SSE handler reads `layout.get_positions()`, the positions reflect the updated topology.

**Polling loop:**

```python
async def run(self) -> None:
    while True:
        try:
            await self._poll_once()
        except Exception:
            logger.debug("Bridge poll error", exc_info=True)
        await asyncio.sleep(self.poll_interval)  # default 0.3s
```

DB reads are offloaded to `asyncio.to_thread` to avoid blocking the event loop. Errors are caught and logged at debug level — the bridge is resilient to missing tables (e.g., when the DB hasn't been initialized yet).

### 6.4 ForceLayout

**Files:** `frontend/graph/layout.py`, `remora_demo/web/graph/layout.py`

`ForceLayout` is a **server-side** force-directed graph layout engine. Unlike client-side D3 layouts, this runs on the server and pushes computed positions to the browser via SSE. CSS transitions on SVG `<g>` elements provide smooth animation (0.5s ease-out) as nodes move.

**Data structures:**

```python
@dataclass
class LayoutNode:
    id: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0        # velocity x
    vy: float = 0.0        # velocity y
    node_type: str = "function"
    pinned: bool = False

@dataclass
class LayoutEdge:
    source: str
    target: str
    edge_type: str = "calls"
```

**Constructor parameters:**

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `width` | 900 | SVG viewport width |
| `height` | 600 | SVG viewport height |
| `repulsion` | 5000.0 | Inverse-square repulsion strength between all node pairs |
| `attraction` | 0.005 | Spring attraction strength for linked pairs |
| `gravity` | 0.02 | Pull toward center |
| `damping` | 0.9 | Velocity damping per iteration |

**`set_graph(nodes, edges)`** — Sets the full graph topology. Preserves positions for existing nodes (stable across topology changes). New nodes are **hierarchy-seeded**: file nodes start at y=100 (top), functions at y≈300 with random x-jitter around center. This ensures the initial layout has a natural top-down hierarchy.

**`step(iterations=1)`** — Runs N iterations of the force simulation. Each iteration applies four forces:

1. **Repulsion** — All pairs, inverse-square: `force = repulsion / (dist² + 1)`. Prevents node overlap.
2. **Attraction** — Linked pairs, spring: `force = attraction * (dist - desired)`. `desired` is 80px for `parent_of` edges, 160px for `calls` edges.
3. **Center gravity** — Pulls all nodes toward `(width/2, height/2)`.
4. **Velocity update** — `v *= damping`, then position update, then clamped to bounds with 40px padding.

Pinned nodes are exempt from all force updates.

**`get_positions()`** — Returns `{node_id: (x, y)}` dict for SVG rendering.

**Performance:** Designed for small graphs (<50 nodes). The O(n²) repulsion is acceptable at this scale. The bridge calls `step(50)` on topology changes and `step(150)` on initial page load for a well-settled layout.

### 6.5 Stario App Factory

**File:** `frontend/graph/app.py`

`create_app()` is the factory function that wires together all components and returns a `(Stario, DBBridge)` tuple. The caller is responsible for starting the bridge as a background task before serving.

**Dependency wiring:**

```python
def create_app(db_path: str = ".remora/indexer.db", poll_interval: float = 0.3) -> tuple[Stario, DBBridge]:
    tracer = RichTracer()
    app = Stario(tracer)
    state = GraphState(db_path=db_path)
    layout = ForceLayout(width=900, height=600)
    relay: Relay = Relay()
    bridge = DBBridge(state=state, layout=layout, relay=relay, poll_interval=poll_interval)

    app.get("/", index(state, layout))
    app.get("/subscribe", subscribe(state, layout, relay))
    app.get("/agent/*", agent_detail(state))
    app.get("/events", event_stream(state))
    app.post("/command", post_command(state))

    return app, bridge
```

**Closure-based DI** — Each handler factory is a function that captures its dependencies and returns an `async def handler(c: Context, w: Writer)` closure. No global state, no dependency injection framework.

**Routes:**

| Route | Method | Handler factory | Purpose |
|-------|--------|-----------------|---------|
| `/` | GET | `index(state, layout)` | Full HTML page with initial graph |
| `/subscribe` | GET | `subscribe(state, layout, relay)` | SSE endpoint — Datastar patches on changes |
| `/agent/*` | GET | `agent_detail(state)` | Sidebar content for selected node (wildcard captures `agent_id`) |
| `/events` | GET | `event_stream(state)` | Event list HTML fragment |
| `/command` | POST | `post_command(state)` | Queue command via `push_command()` |

**`CommandSignals` dataclass** — Parsed from Datastar signals on POST:

```python
@dataclass
class CommandSignals:
    command_type: str = ""   # "chat", "approve", "reject"
    agent_id: str = ""       # Target agent
    payload: str = ""        # JSON string with command-specific data
```

**Handler details:**

**`index`** — On page load, reads a snapshot, seeds the layout (`step(150)` iterations), and returns the full HTML shell with embedded SVG.

**`subscribe`** — The SSE long-poll handler. Sends an initial patch with current graph SVG and event list, then enters a loop: `async for subject, _ in w.alive(relay.subscribe("graph.*"))`. On each relay notification, reads fresh data and sends Datastar patches. The `w.alive()` context detects client disconnection.

**`agent_detail`** — Extracts `agent_id` from `c.req.tail` (Stario wildcard path tail). Reads node, events, proposals, and connections in parallel via `asyncio.to_thread`, then renders the sidebar panel. Returns full HTML (not SSE patch) since this is triggered by a `data-on-click="@get('/agent/{id}')"` Datastar action.

**`post_command`** — Reads `CommandSignals` from `c.signals()`, validates, then calls `state.push_command()`. Returns JSON `{status: "queued", command_id: N}`.

**Usage pattern:**

```python
app, bridge = create_app("/path/to/indexer.db")
asyncio.create_task(bridge.run())
await app.serve(host="127.0.0.1", port=8080)
```

### 6.6 SVG Rendering

**Files:** `frontend/graph/svg.py`, `remora_demo/web/graph/svg.py`

All graph rendering produces plain SVG strings — no Stario dependency, fully testable with Python 3.13. The handlers wrap results in `SafeString` before passing to `w.patch()`.

**Catppuccin Mocha palette:**

| Status | Color | Hex |
|--------|-------|-----|
| `active` | Green | `#a6e3a1` |
| `idle` | Gray | `#6c7086` |
| `running` | Blue | `#89b4fa` |
| `pending_approval` | Yellow | `#f9e2af` |
| `error` | Red | `#f38ba8` |
| `orphaned` | Dark gray | `#45475a` |

**Node radius by type:**

| Type | Radius (px) |
|------|-------------|
| `file` | 14 |
| `class` | 11 |
| `function` | 8 |
| `method` | 8 |

**Edge styles:**

| Type | Stroke | Width | Opacity | Dash |
|------|--------|-------|---------|------|
| `parent_of` | `#585b70` | 1.5 | 0.5 | solid |
| `calls` | `#89b4fa` | 1.0 | 0.4 | `6,4` (dashed) |

**SVG primitives** — Low-level builder functions returning strings:

| Function | Produces |
|----------|----------|
| `svg_open(width, height)` | `<svg>` with `viewBox`, `preserveAspectRatio` |
| `svg_close()` | `</svg>` |
| `svg_circle(r, fill, stroke, ...)` | `<circle>` with optional stroke, filter |
| `svg_line(x1, y1, x2, y2, ...)` | `<line>` with stroke, dash, opacity |
| `svg_text(content, dy, font_size)` | `<text>` centered below node |
| `svg_group_open(transform, class_name, data_attrs)` | `<g>` with transform, Datastar data attributes |
| `svg_group_close()` | `</g>` |
| `svg_rect(x, y, width, height, ...)` | `<rect>` |
| `svg_defs_glow_filter()` | `<defs><filter id="glow">` — Gaussian blur + color matrix for focused node |

**Composite builders:**

**`render_node(node_id, x, y, node, cursor_focus, selected_node)`** — Renders a single node as a `<g>` group containing a circle and label text. The group has `transform="translate(x,y)"` for positioning and `data-on-click="@get('/agent/{node_id}')"` for Datastar click handling. Focused nodes get a blue stroke + glow filter. Selected nodes get a lavender stroke. Long names are truncated to 16 characters.

**`render_edge(edge, positions, cursor_focus, selected_node)`** — Renders a single edge as a `<line>`. Active edges (connected to focused/selected node) get increased width (+1px) and higher opacity (0.9).

**`render_graph_svg(nodes, edges, positions, cursor_focus, selected_node, width, height)`** — Composes the full SVG: opens SVG, adds glow filter defs, renders all edges (drawn first, behind nodes), renders all nodes (on top), closes SVG. The SVG element has `id="graph-svg"` for Datastar morphing.

### 6.7 Views

**Files:** `frontend/graph/views/` (`shell.py`, `graph.py`, `sidebar.py`, `event_stream.py`)

All view functions return **plain HTML strings** — no Stario imports. Handlers in `app.py` wrap them in `SafeString` for `w.patch()` or pass them directly to `w.html()`.

#### Shell View (`views/shell.py`)

`render_shell(snapshot, positions)` — Returns the complete `<!DOCTYPE html>` page:

```
<html>
  <head>
    <script> Datastar CDN (v1.0.0-RC.7) </script>
    <style> graph_css() — full Catppuccin Mocha theme </style>
  </head>
  <body data-on-load="@get('/subscribe')">
    <div class="app" data-signals='{"activeTab": "log", "chatMessage": ""}'>
      <header class="header"> title + node/edge count </header>
      <div class="main">
        <div class="graph-pane" id="graph-pane"> initial SVG </div>
        <div class="sidebar" id="sidebar">
          <div id="sidebar-content"> placeholder </div>
          <div id="event-stream"> placeholder </div>
        </div>
      </div>
    </div>
    <script> zoom/pan JS </script>
  </body>
</html>
```

**Datastar signals**: `activeTab` (controls sidebar tab visibility via `data-show`), `chatMessage` (bound to textarea via `data-model`).

**Zoom/pan JS**: Client-side mouse wheel zoom (0.2x–4x scale) and drag-to-pan on the graph pane. `mousedown` on `.node-group` elements is excluded (allows click-through to Datastar actions).

#### Graph View (`views/graph.py`)

`render_graph(snapshot, positions, cursor_focus, selected_node)` — Thin wrapper around `svg.render_graph_svg()`. Normalizes edges to dicts. Returns an SVG string with `id="graph-svg"` for Datastar morphing.

#### Sidebar View (`views/sidebar.py`)

`render_sidebar_content(node, events, proposals, connections)` — Renders the sidebar detail panel for a selected node. Returns a `<div id="sidebar-content">` that replaces the existing element via Datastar morph.

**Structure:**

1. **Header** — Node name, type badge, status badge (color-coded)
2. **Metadata** — ID, file path, line range
3. **Tabs** — Four Datastar-controlled tabs via `data-on-click="$activeTab = '...'"`
4. **Log tab** (`data-show="$activeTab == 'log'"`) — Last 15 events for this agent, each with type badge, timestamp, and message preview (truncated to 80 chars)
5. **Source tab** (`data-show="$activeTab == 'source'"`) — Source code in a `<pre><code>` block, HTML-escaped
6. **Connections tab** (`data-show="$activeTab == 'connections'"`) — Parents, children, callers, callees as clickable items (`data-on-click="@get('/agent/{id}')"`)
7. **Actions tab** (`data-show="$activeTab == 'actions'"`) — Chat input (textarea bound to `$chatMessage`) with send button, and pending proposals with approve/reject buttons. Both post to `/command` via Datastar.

**Status colors** mirror SVG palette: green=active, gray=idle, blue=running, yellow=pending_approval, red=error.

#### Event Stream View (`views/event_stream.py`)

`render_event_list(events)` — Renders the global event firehose at the bottom of the sidebar. Returns a `<div id="event-stream">` for Datastar morphing.

Each event item shows:
- **Type badge** — Color-coded by event type (13 types mapped to Catppuccin colors)
- **Agent ID** — Shown in lavender
- **Timestamp** — `HH:MM:SS.mmm` format (millisecond precision)
- **Message body** — Truncated to 100 chars, shown in subtext color

**Event type color mapping:**

| Event Type | Color | Meaning |
|-----------|-------|---------|
| `NodeDiscovered` | Green | New agent found |
| `NodeRemoved` | Gray | Agent removed |
| `AgentStart` | Blue | Agent turn started |
| `AgentComplete` | Green | Agent turn completed |
| `AgentError` | Red | Agent error |
| `ContentChanged` | Yellow | File content changed |
| `ModelRequest`/`ModelResponse` | Purple | LLM interaction |
| `AgentMessage` | Teal | Inter-agent message |
| `HumanChat` | Orange | Human interaction |
| `RewriteProposal` | Yellow | Code change proposed |
| `RewriteApplied` | Green | Proposal accepted |
| `RewriteRejected` | Red | Proposal rejected |

### CSS Theme (`css.py`)

`graph_css()` returns the complete CSS as a string, inlined into the HTML shell's `<style>` tag. Key design choices:

- **Catppuccin Mocha** dark theme with CSS custom properties (`--bg: #1e1e2e`, `--surface: #313244`, etc.)
- **JetBrains Mono** monospace font family with Fira Code fallback
- **CSS transitions on SVG** — `transform 0.5s ease-out` on `.node-group`, `fill 0.3s` on `.node-circle`. This creates smooth animation when the server pushes new positions via SSE patches.
- **Pulse animation** — Running nodes (`fill='#89b4fa'`) get a 1.5s CSS pulse animation
- **Full-viewport layout** — `height: 100vh`, flex column, no scroll on body. Graph pane fills remaining space.
- **Sidebar** — Fixed 350px width, scrollable, with tabbed detail panel and event stream

## 7. Crossover Interfaces

Every non-trivial system has boundaries — the seams where data changes shape as it moves between subsystems. This section catalogs every crossover in Remora: the data shape on each side, the conversion logic, and the constraints to watch for.

### 7.1 Event Serialization Boundary

Events cross the Pydantic → JSON → SQLite → JSON → dict boundary during storage and retrieval.

**Write path** (`EventStore.append()` → `_serialize_event()`):

```
Pydantic event (frozen BaseModel)
    │
    ▼  event.model_dump()           ← Pydantic path (preferred)
dict[str, Any]
    │
    ▼  json.dumps(data, default=str)
JSON string
    │
    ▼  INSERT INTO events (... payload ...)
SQLite TEXT column
```

The serializer has a three-tier fallback in `_serialize_event()` (`event_store.py:665-677`):

1. **Pydantic model** — `hasattr(event, "model_dump")` → `event.model_dump()`
2. **Dataclass** — `is_dataclass(event)` → `dataclasses.asdict(event)`
3. **Plain object** — `hasattr(event, "__dict__")` → `dict(vars(event))`
4. **Fallback** — `{"value": str(event)}`

This matters because the EventStore accepts both `RemoraEvent` (Pydantic) and `structured_agents.events.Event` (which may be dataclasses or plain objects). The `default=str` in `json.dumps` handles types like `Path` or `datetime` that aren't natively JSON-serializable.

**Routing field extraction** happens via `getattr` at append time (`event_store.py:278-282`):

```python
from_agent = getattr(event, "from_agent", None)
to_agent = getattr(event, "to_agent", None)
correlation_id = getattr(event, "correlation_id", None)
tags = getattr(event, "tags", None)
tags_json = json.dumps(tags) if tags else None
```

These are stored as separate indexed columns for efficient querying, while the full event payload is also in the `payload` TEXT column (denormalized).

**Read path** (`EventStore._row_to_dict()`):

```
SQLite Row
    │
    ▼  row["payload"]
JSON string
    │
    ▼  json.loads(row["payload"])
dict[str, Any]
    │
    ▼  merged with routing columns
dict with: id, graph_id, event_type, payload (dict),
           timestamp, created_at, from_agent, to_agent,
           correlation_id, tags (list | None)
```

Note that `tags` is stored as a JSON-encoded string in the `tags` column — it's `json.loads()`-ed back to a list on read. Events are **not** reconstituted into typed Pydantic models on read — they come back as plain dicts. This is intentional: the read side (web UI, replay API) only needs the data, not the type constraints.

**Key constraint**: Event payloads are **append-only**. Once written, a row is never updated. The `events` table has no UPDATE queries anywhere in the codebase.

### 7.2 EventStore to EventBus

After an event is persisted to SQLite and committed, the EventStore notifies the in-process EventBus. This is a **fire-and-forget** notification — the bus is optional and its failure doesn't affect persistence.

**Sequence** (in `EventStore.append()`, lines 284-316):

```
1. INSERT event into events table     ← under asyncio.Lock
2. Apply projection (UPSERT nodes)    ← same transaction
3. COMMIT                             ← releases lock
4. Match subscriptions → trigger queue ← OUTSIDE transaction
5. EventBus.emit(event)               ← OUTSIDE transaction
```

Steps 4 and 5 happen **after** the transaction commits, so they never block writes. The EventBus receives the original typed event object (not the serialized dict), so handlers get full Pydantic model access.

**EventBus dispatch** (`event_bus.py:37-60`):

```python
async def emit(self, event):
    # Collect handlers: type-matched + wildcard (subscribe_all)
    handlers = []
    for registered_type, registered_handlers in self._handlers.items():
        if isinstance(event, registered_type):
            handlers.extend(registered_handlers)
    handlers.extend(self._all_handlers)
    
    for handler in handlers:
        result = handler(event)
        if asyncio.iscoroutine(result):
            await result
```

Handlers can be sync or async — the bus auto-detects and awaits coroutines. The error policy is configurable: `"log"` (default, swallows exceptions with a warning) or `"propagate"` (re-raises).

**Consumers of EventBus**:
- `UiStateProjector.record()` — subscribed via `subscribe_all`, reduces every event into UI state
- `EventBus.stream()` context manager — used by `RemoraService.subscribe_stream()` and `events_stream()` for SSE
- `EventBus.wait_for()` — blocks until a matching event arrives (used for request/response patterns)

### 7.3 EventStore to SubscriptionRegistry to Trigger Queue

This is the reactive routing chain that determines which agents should wake up when an event is stored.

**Flow** (in `EventStore.append()`, lines 302-312):

```
Event committed to SQLite
    │
    ▼  self._subscriptions.get_matching_agents(event)
SubscriptionRegistry
    │  1. Rebuild cache if invalidated (self._cache is None)
    │  2. Look up event_type in cache → list[(agent_id, SubscriptionPattern)]
    │  3. Also include wildcard entries (cache key "")
    │  4. pattern.matches(event) for each candidate
    │  5. Deduplicate by agent_id
    │
    ▼  Returns list[str] of matching agent IDs
    │
    ▼  For each agent_id:
    │     self._trigger_queue.put((agent_id, event_id, event))
    │
asyncio.Queue[tuple[str, int, RemoraEvent]]
    │
    ▼  Consumed by AgentRunner via EventStore.get_triggers()
```

**Cache structure** (`subscriptions.py:128`):

```python
_cache: dict[str, list[tuple[str, SubscriptionPattern]]] | None
```

Keys are event type names (e.g., `"ContentChangedEvent"`). The empty string key `""` holds wildcard subscriptions (no `event_types` filter). The cache is rebuilt from the `subscriptions` table on first access and invalidated (`self._cache = None`) on any mutation (register, unregister).

**SubscriptionPattern matching** (`subscriptions.py:40-74`) checks fields in order:
1. `event_types` — event type name must be in the list (or field is None = match all)
2. `from_agents` — event's `from_agent` must be in the list
3. `to_agent` — event's `to_agent` must match exactly
4. `path_glob` — event's `path` is normalized and matched with `PurePath.match()`
5. `tags` — any overlap between event tags and pattern tags

All checks are AND-ed. A `None` field means "don't filter on this dimension."

**Default subscriptions** — `register_defaults(agent_id, file_path)` creates two:
1. Direct message: `SubscriptionPattern(to_agent=agent_id)` — matches any event addressed to this agent
2. Source file: `SubscriptionPattern(event_types=["ContentChangedEvent"], path_glob=file_path)` — wake when the agent's source file changes

**Shared connection mode**: When the SubscriptionRegistry is created with `connection=` and `lock=` from the EventStore, it shares the same SQLite connection. The subscriptions table is created by `EventStore.initialize()`, and the registry skips its own `initialize()`. This eliminates cross-database coordination.

### 7.4 AgentNode Triple Interface

`AgentNode` is the single model that speaks three completely different protocols:

**Interface 1: SQLite** — `to_row()` / `from_row()`

`to_row()` (`agent_node.py:104-112`) serializes the Pydantic model to a flat dict suitable for SQLite INSERT. List and nested Pydantic model fields are JSON-encoded:

```python
def to_row(self) -> dict[str, Any]:
    data = self.model_dump()
    data["caller_ids"] = json.dumps(data["caller_ids"])        # list[str] → JSON
    data["callee_ids"] = json.dumps(data["callee_ids"])        # list[str] → JSON
    data["extra_tools"] = json.dumps(                          # list[ToolSchema] → JSON
        [t.model_dump() for t in self.extra_tools]
    )
    data["extra_subscriptions"] = json.dumps(                  # list[SubscriptionPattern] → JSON
        [s.model_dump() for s in self.extra_subscriptions]
    )
    data["mounted_workspaces"] = json.dumps(data["mounted_workspaces"])  # list[str] → JSON
    return data
```

`from_row()` (`agent_node.py:114-125`) reverses the process:

```python
@classmethod
def from_row(cls, row: sqlite3.Row | dict) -> AgentNode:
    data = dict(row)
    data["caller_ids"] = json.loads(data.get("caller_ids") or "[]")
    data["callee_ids"] = json.loads(data.get("callee_ids") or "[]")
    data["extra_tools"] = [ToolSchema(**t) for t in json.loads(data.get("extra_tools") or "[]")]
    data["extra_subscriptions"] = [
        SubscriptionPattern(**s) for s in json.loads(data.get("extra_subscriptions") or "[]")
    ]
    data["mounted_workspaces"] = json.loads(data.get("mounted_workspaces") or "[]")
    return cls(**data)
```

The `or "[]"` fallback handles NULL/missing columns from older database schemas.

**Interface 2: LLM** — `to_system_prompt()`

Generates a multi-section Markdown prompt (`agent_node.py:139-169`):

```
You are an autonomous AI agent embodying a Python function: `my_func`

# Identity
- Node ID: src/foo.py:my_func:10:25
- Location: src/foo.py:10-25
- Parent: src/foo.py:MyClass:5:50

# Your Source Code
```python
def my_func(self): ...
```

# Graph Context
- Called by: src/bar.py:caller:1:10
- You call: src/baz.py:helper:5:15

# Core Rules
1. You may ONLY edit your own body using `rewrite_self()`.
2. To request changes elsewhere, use `message_node(target_id, request)`.
3. All edits are proposals -- the human must approve before they apply.

# Specialization (my_extension)
<custom_system_prompt content>

# Available Workspaces
- /path/to/workspace1
```

Language detection uses file extension → `(display_name, fence_language)` mapping for 10 supported languages.

**Interface 3: LSP** — `to_code_lens()`, `to_hover()`, `to_code_actions()`, `to_document_symbol()`

These methods convert to `lsprotocol.types` objects. They use deferred imports (`from lsprotocol import types as lsp`) so the LSP dependency is only required when these methods are actually called.

| Method | Returns | LSP Feature |
|--------|---------|-------------|
| `to_code_lens()` | `lsp.CodeLens` | Status icon + node ID above the function, with `remora.selectAgent` command |
| `to_hover()` | `lsp.Hover` | Markdown panel showing ID, type, status, parent, callers, callees, recent events |
| `to_code_actions()` | `list[lsp.CodeAction]` | 3 built-in actions (chat, rewrite, message) + 1 per `extra_tools` entry |
| `to_document_symbol()` | `lsp.DocumentSymbol` | Symbol with `name [status]` and appropriate `SymbolKind` |

Status icons: `●` idle, `▶` running, `⏸` pending_approval, `○` error.

### 7.5 Unified SQLite as Shared State Bus

The single `indexer.db` file serves as an inter-process communication channel. Multiple processes can read and write concurrently thanks to SQLite WAL (Write-Ahead Logging) mode.

**Process topology:**

```
┌─────────────────┐    ┌────────────────┐    ┌──────────────────┐
│  LSP Server      │    │  Web Service   │    │  Graph Viewer    │
│  (Neovim)        │    │  (Starlette)   │    │  (Stario)        │
│                  │    │                │    │                  │
│  EventStore      │    │  RemoraService │    │  GraphState      │
│  (read/write)    │    │  (read/write)  │    │  (read-only)     │
│                  │    │                │    │                  │
│  RemoraDB        │    │                │    │  push_command()  │
│  (read/write)    │    │                │    │  (write, via     │
│                  │    │                │    │   separate conn)  │
└────────┬─────────┘    └───────┬────────┘    └────────┬─────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │  .remora/indexer.db    │
                    │  WAL mode             │
                    │  8 tables             │
                    └───────────────────────┘
```

**WAL mode pragmas** (set by both `EventStore.initialize()` and `RemoraDB.__init__()` in standalone mode):

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

WAL allows concurrent readers while one writer holds the write lock. This is critical because the graph viewer polls the DB every 300ms while the LSP server is actively writing events.

**GraphState's read-only access** (`state.py`): Opens its connection with `?mode=ro` URI or simply uses `PRAGMA query_only=ON` semantics — all reads are offloaded to threads via `asyncio.to_thread`. The one exception is `push_command()`, which writes to the `command_queue` table using a **separate writable connection** that is opened on-demand.

**Consistency model**: There is no distributed transaction protocol. Each process sees a snapshot-consistent view at the time of its last read. The graph viewer's 300ms polling interval means it may be up to 300ms behind the latest writes. For the UI this is imperceptible.

### 7.6 command_queue Table

The `command_queue` table is the **asynchronous command channel** from the web frontend to the LSP server's `AgentRunner`.

**Write side** (Graph Viewer → SQLite):

The graph viewer's `/command` POST handler (`app.py:133-153`) receives `CommandSignals` from the browser (via Datastar signals), then calls `state.push_command()`:

```python
cmd_id = state.push_command(command_type, agent_id, payload)
```

`GraphState.push_command()` opens a **separate writable connection** (distinct from the read-only connection used for queries) and inserts:

```sql
INSERT INTO command_queue (command_type, agent_id, payload, status, created_at)
VALUES (?, ?, ?, 'pending', ?)
```

In `RemoraDB`, the equivalent `push_command()` (`db.py:247-258`) is synchronous (not decorated with `@async_db`) and commits immediately.

**Read side** (LSP Server polls):

`RemoraDB.poll_commands(limit=10)` (`db.py:260-267`):

```sql
SELECT * FROM command_queue WHERE status = 'pending' ORDER BY id ASC LIMIT ?
```

After processing each command, `mark_command_done(command_id)` updates:

```sql
UPDATE command_queue SET status = 'done', processed_at = ? WHERE id = ?
```

**Command types**: `chat` (send message to agent), `approve` (accept proposal), `reject` (reject proposal with feedback).

**Lifecycle**: pending → done. Commands are never deleted — the `processed_at` timestamp records when they were consumed. This provides an audit trail.

### 7.7 cursor_focus Table

The `cursor_focus` table is a **single-row table** that tracks the Neovim cursor position for the graph viewer to highlight the corresponding node.

**Write side** — Neovim → LSP Server → SQLite:

The `$/remora/cursorMoved` custom notification (`notifications.py:7-26`) fires whenever the cursor moves in Neovim. The handler:

1. Extracts `uri` and `line` from params
2. Queries `EventStore.get_node_at_position(uri, line)` to find the narrowest node containing that line
3. Calls `RemoraDB.update_cursor_focus(agent_id, uri, line)`:

```sql
INSERT OR REPLACE INTO cursor_focus (id, agent_id, file_path, line, timestamp)
VALUES (1, ?, ?, ?, ?)
```

The `CHECK (id = 1)` constraint ensures only one row ever exists. `INSERT OR REPLACE` is an atomic upsert.

**Read side** — Graph Viewer polls:

`DBBridge._read_fingerprints()` reads `SELECT timestamp FROM cursor_focus WHERE id = 1`. When the timestamp changes, it publishes `"graph.cursor"` to the Relay, which triggers the SSE handler to re-render the graph SVG with the focused node highlighted (glow filter).

`GraphState.read_snapshot()` also reads the cursor_focus row and includes it in `GraphSnapshot.cursor_focus` as `dict | None` with keys `agent_id`, `file_path`, `line`, `timestamp`.

### 7.8 HTTP/SSE API Boundary

Two separate HTTP servers expose data to browsers. Their routes and data shapes are distinct.

**Web Demo Service** (Starlette adapter, `adapters/starlette.py`):

| Route | Method | Response | Data Shape |
|-------|--------|----------|------------|
| `/` | GET | HTML | Full dashboard (render_shell + render_dashboard) |
| `/subscribe` | GET | SSE (DatastarResponse) | Datastar merge fragments (HTML patches) |
| `/events` | GET | SSE | `event: {type}\ndata: {json}\n\n` per event |
| `/replay` | GET | SSE | `event: replay\ndata: {json}\n\n`, optional `?follow=true` for live tail |
| `/input` | POST | JSON | `{"request_id": str, "response": str}` → `InputResponse.to_dict()` |
| `/config` | GET | JSON | `ConfigSnapshot.to_dict()` |
| `/snapshot` | GET | JSON | UI state dict from `UiStateProjector` |
| `/swarm/agents` | GET | JSON | `list[dict]` — all agents with `model_dump()` |
| `/swarm/agents/{id}` | GET | JSON | Single agent dict |
| `/swarm/events` | POST | JSON | Emit event: `{"event_type": str, "data": dict}` |
| `/swarm/subscriptions/{id}` | GET | JSON | Agent's subscription list |

SSE responses include standard headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`.

The `/subscribe` endpoint uses `DatastarResponse` from `datastar_py.starlette` — it wraps the async generator in a Starlette `StreamingResponse` with Datastar-specific SSE formatting (merge fragments with `id` and `selector` for DOM morphing).

The `/events` endpoint uses raw SSE formatting: each event is `normalize_event(event)` → JSON, yielded as `event: {type}\ndata: {json}\n\n`.

**Graph Viewer** (Stario, `app.py`):

| Route | Method | Response | Data Shape |
|-------|--------|----------|------------|
| `/` | GET | HTML | Full page via `render_shell()` |
| `/subscribe` | GET | SSE | Datastar patches via `w.patch(SafeString(...))` |
| `/agent/*` | GET | HTML | Sidebar content fragment |
| `/events` | GET | HTML | Event list fragment |
| `/command` | POST | JSON | `CommandSignals` → `{"status": "queued", "command_id": int}` |

The Stario `/subscribe` handler uses `w.alive(relay.subscribe("graph.*"))` — it yields whenever the Relay receives a publish on any `graph.*` subject. On each yield, it re-reads the DB snapshot and sends updated SVG/HTML fragments via `w.patch()`.

### 7.9 DBBridge Polling Loop

The `DBBridge` is the adapter that converts SQLite state changes into Relay publications, which in turn drive SSE pushes to the browser.

**Polling cycle** (`bridge.py:49-57`):

```python
async def run(self):
    while True:
        await self._poll_once()
        await asyncio.sleep(self.poll_interval)   # default 0.3s
```

**Fingerprint computation** (`bridge.py:104-134`):

```python
def _read_fingerprints(self) -> dict[str, str]:
    # nodes: "count:max_rowid"
    cursor.execute("SELECT count(*), max(rowid) FROM nodes")
    fp["nodes"] = f"{row[0]}:{row[1]}"
    
    # node_status: concatenated status strings (excludes 'orphaned')
    cursor.execute("SELECT group_concat(status) FROM (...)")
    fp["node_status"] = str(cursor.fetchone()[0])
    
    # edges: "count:max_rowid"
    cursor.execute("SELECT count(*), max(rowid) FROM edges")
    fp["edges"] = f"{row[0]}:{row[1]}"
    
    # cursor: timestamp from cursor_focus
    cursor.execute("SELECT timestamp FROM cursor_focus WHERE id = 1")
    fp["cursor"] = str(row[0]) if row else "0"
    
    # events: max rowid
    cursor.execute("SELECT max(rowid) FROM events")
    fp["events"] = str(cursor.fetchone()[0])
```

**Change detection** — compares current fingerprints to `self._last_fp`:

| Fingerprint Change | Subject Published | What Updates |
|-------------------|-------------------|--------------|
| `nodes` or `edges` changed | `graph.topology` | Full re-layout (50 incremental steps) + SVG re-render |
| `node_status` changed | `graph.status` | SVG re-render (node colors) |
| `cursor` changed | `graph.cursor` | SVG re-render (glow filter on focused node) |
| `events` changed | `graph.events` | Event stream panel re-render |

On topology changes, the bridge also updates the force layout: re-reads the snapshot, calls `layout.set_graph()`, runs `layout.step(50)` for incremental settling.

**Relay publish**: `relay.publish(subject, "changed")` — the data payload is always just `"changed"`. The SSE handler re-reads the current state from the DB; the Relay merely signals that something changed.

### 7.10 Cairn Externals Interface

`CairnExternals` (`cairn_externals.py`) wraps the Cairn filesystem API with path normalization, providing a bridge between Remora's project-relative paths and Cairn's workspace-relative paths.

**Architecture:**

```
Agent Tool (e.g., rewrite_self)
    │
    ▼  AgentContext.cairn_externals["read_file"]
CairnExternals.read_file(path)
    │
    ▼  self._normalize(path)  →  PathResolver.to_workspace_path(path)
    │     Converts absolute/project-relative → workspace-relative POSIX
    │
    ▼  self._delegate.read_file(normalized_path)
CairnExternalFunctions (Cairn SDK)
    │
    ▼  agent_fs or stable_fs
Filesystem (copy-on-write workspace)
```

**`PathResolver.to_workspace_path()`** (`path_resolver.py:39-53`):
- Absolute path → strip project root → POSIX
- Relative path → strip leading `/` → POSIX
- Outside project root → warning + absolute path with leading `/` stripped

**8 externals exposed** via `as_externals()`:

| Key | Signature | Purpose |
|-----|-----------|---------|
| `read_file` | `(path: str) → str` | Read file content |
| `write_file` | `(path: str, content: str) → bool` | Write file content |
| `list_dir` | `(path: str = ".") → list[str]` | List directory |
| `file_exists` | `(path: str) → bool` | Check file existence |
| `search_files` | `(pattern: str) → list[str]` | Glob search (no normalization) |
| `search_content` | `(pattern: str, path: str = ".") → list[Any]` | Grep-like content search |
| `submit_result` | `(summary: str, changed_files: list[str]) → bool` | Finalize workspace |
| `log` | `(message: str) → bool` | Log a message |

All methods except `search_files` normalize paths through `PathResolver`. `search_files` passes the raw glob pattern directly to the Cairn delegate.

**Integration with AgentContext**: `CairnExternals.as_externals()` returns the dict of callables. This dict is passed to `AgentContext(cairn_externals=...)`. When `AgentContext.as_externals()` is called for Grail compatibility, it merges Cairn externals with swarm callback keys (agent_id, emit_event, etc.).

### 7.11 LSP Custom Notifications

Remora defines custom LSP notifications under the `$/remora/` namespace. These are bidirectional between Neovim and the LSP server.

**`$/remora/cursorMoved`** — Neovim → Server (`notifications.py:7-26`)

Sent by the Neovim client plugin whenever the cursor moves to a new position.

```typescript
// Params shape (from Neovim)
{
    "uri": string,     // File URI (e.g., "file:///path/to/file.py")
    "line": number     // 1-based line number
}
```

Handler behavior:
1. Normalize params (may arrive as dict or attrs Object from pygls)
2. `event_store.get_node_at_position(uri, line)` — finds narrowest node containing the line
3. `db.update_cursor_focus(agent_id, uri, line)` — writes to single-row cursor_focus table

This is read-only from the LSP server's perspective (no response sent back). The effect is visible in the graph viewer via cursor_focus polling.

**`$/remora/submitInput`** — Neovim → Server (`notifications.py:29-92`)

Sent when the user submits input via the Neovim UI (chat message or proposal feedback).

```typescript
// Chat message
{
    "agent_id": string,   // Target agent
    "input": string       // User message
}

// Proposal rejection feedback
{
    "proposal_id": string,  // Proposal being rejected
    "input": string         // Rejection feedback
}
```

For chat: Emits a `HumanChatEvent(agent_id, to_agent, message, correlation_id)` and triggers the runner.

For rejection: Emits a `RewriteRejectedEvent(agent_id, proposal_id, feedback, correlation_id)` and triggers the runner with `context={"rejection_feedback": feedback}`.

**`$/remora/event`** — Server → Neovim

Sent by `emit_event()` in the server to notify the client of new events (used for UI updates in the Neovim plugin).

**`$/remora/agentsUpdated`** — Server → Neovim

Sent by `notify_agents_updated()` after node discovery or status changes, prompting the client to refresh code lenses and diagnostics.

### 7.12 AgentContext Callback Boundary

`AgentContext` (`agent_context.py`) is the typed boundary between swarm tools and the Remora system. Every tool invocation goes through these callbacks rather than reaching into internals directly.

**Callback signatures:**

```python
EmitEventFn    = Callable[[str, Any], Coroutine[Any, Any, None]]
    # (graph_id, event) → None
    
RegisterSubFn  = Callable[[str, Any], Coroutine[Any, Any, None]]
    # (agent_id, pattern) → None

UnsubscribeFn  = Callable[[int], Coroutine[Any, Any, str]]
    # (subscription_id) → agent_id

BroadcastFn    = Callable[[str, str], Coroutine[Any, Any, str]]
    # (content, tags_json) → broadcast result

QueryAgentsFn  = Callable[[str | None], Coroutine[Any, Any, list[Any]]]
    # (filter_type | None) → list of agent dicts
```

**How tools use AgentContext**: The 5 swarm tools (`send_message`, `subscribe`, `unsubscribe`, `broadcast`, `query_agents`) are passed the AgentContext at construction time. Each tool calls through the appropriate callback. For example, `send_message` calls `context.emit_event(graph_id, AgentMessageEvent(...))`.

**`as_externals()` bridge** (`agent_context.py:44-62`):

For backward compatibility with Grail scripts that expect a flat `dict[str, Any]`, `AgentContext.as_externals()` merges:

1. `self.cairn_externals` — filesystem callbacks (read_file, write_file, etc.)
2. Swarm keys overlay:
   - `agent_id`, `correlation_id`
   - `emit_event`, `register_subscription`, `unsubscribe_subscription`
   - `broadcast`, `query_agents`

Swarm keys are applied **after** cairn externals, so they take precedence if there's a name collision (there shouldn't be, but the ordering is intentional).

**Who constructs AgentContext**: The `AgentRunner` builds an `AgentContext` for each agent turn, wiring the callbacks to the current `EventStore`, `SubscriptionRegistry`, and `CairnExternals` instances. The context is scoped to a single agent execution — `agent_id` and `correlation_id` are set per-turn.

## 8. Unified SQLite Database

All persistent state lives in a single SQLite database file (`.remora/indexer.db`). The schema is created by `EventStore.initialize()` (`event_store.py:56-208`) in a single `executescript` call sequence. WAL mode is enabled for concurrent read/write access.

There are **8 tables** organized into two logical groups:

- **Core tables** (owned by EventStore): `events`, `nodes`, `subscriptions`
- **Operational tables** (used by RemoraDB): `edges`, `activation_chain`, `proposals`, `cursor_focus`, `command_queue`

Both `SubscriptionRegistry` and `RemoraDB` can share the EventStore's connection in "shared mode" to avoid opening multiple connections to the same file.

### 8.1 events Table

The append-only event log. Every event in the system is recorded here.

```sql
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL,       -- JSON-encoded event data
    timestamp       REAL NOT NULL,       -- Event timestamp (from event object)
    created_at      REAL NOT NULL,       -- DB insertion time
    from_agent      TEXT,                -- Routing: source agent
    to_agent        TEXT,                -- Routing: target agent
    correlation_id  TEXT,                -- Causation chain ID
    tags            TEXT                 -- JSON-encoded list of tags
);
```

**Indexes:**

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_events_graph_id` | `graph_id` | Filter events by execution graph |
| `idx_events_type` | `event_type` | Filter by event type (e.g., `"AgentStartEvent"`) |
| `idx_events_timestamp` | `timestamp` | Time-range queries, ordering |
| `idx_events_to_agent` | `to_agent` | Directed message lookup |

**Routing fields**: `from_agent`, `to_agent`, `correlation_id`, and `tags` are extracted from event attributes via `getattr()` at insert time and stored as denormalized columns. They duplicate data that's also inside the `payload` JSON, but the separate columns enable indexed queries without JSON parsing.

**Migration**: `_migrate_routing_fields()` adds these columns to databases created before routing was introduced, using `ALTER TABLE ADD COLUMN`.

**Access patterns:**
- `append()` — INSERT + projection + commit (under asyncio.Lock)
- `replay()` — SELECT with optional filters (graph_id, event_types, since/until, after_id), ordered by timestamp ASC
- `get_recent_events()` — SELECT WHERE from_agent = ? OR to_agent = ?, ordered DESC, LIMIT
- `get_events_for_correlation()` — SELECT WHERE correlation_id = ?, ordered ASC
- `get_event_count()` — COUNT(*) for a graph_id
- `delete_graph()` — DELETE all events for a graph_id

**Key constraint**: Rows are **never updated**. This table is truly append-only.

### 8.2 nodes Table

The materialized view of agent state, maintained by `NodeProjection`. Each row represents one discovered code node (function, class, method, or file).

```sql
CREATE TABLE IF NOT EXISTS nodes (
    node_id              TEXT PRIMARY KEY,  -- e.g. "src/foo.py:my_func:10:25"
    node_type            TEXT NOT NULL,     -- "function", "class", "method", "file", "section", "table"
    name                 TEXT NOT NULL,     -- Short name (e.g. "my_func")
    full_name            TEXT NOT NULL,     -- Qualified name (e.g. "MyClass.my_func")
    file_path            TEXT NOT NULL,     -- Relative path to source file
    start_line           INTEGER NOT NULL,
    end_line             INTEGER NOT NULL,
    start_byte           INTEGER NOT NULL DEFAULT 0,
    end_byte             INTEGER NOT NULL DEFAULT 0,
    source_code          TEXT NOT NULL,     -- Full source text of the node
    source_hash          TEXT NOT NULL,     -- Hash for change detection
    parent_id            TEXT,              -- FK to parent node (class for methods, file for top-level)
    caller_ids           TEXT NOT NULL DEFAULT '[]',   -- JSON: list[str]
    callee_ids           TEXT NOT NULL DEFAULT '[]',   -- JSON: list[str]
    status               TEXT NOT NULL DEFAULT 'idle', -- "idle", "running", "error", "pending_approval"
    last_trigger_event   TEXT NOT NULL DEFAULT '',
    last_completed_at    REAL,
    extension_name       TEXT,              -- Which extension config matched
    custom_system_prompt TEXT NOT NULL DEFAULT '',
    mounted_workspaces   TEXT NOT NULL DEFAULT '[]',   -- JSON: list[str]
    extra_tools          TEXT NOT NULL DEFAULT '[]',   -- JSON: list[ToolSchema]
    extra_subscriptions  TEXT NOT NULL DEFAULT '[]'    -- JSON: list[SubscriptionPattern]
);
```

**Indexes:**

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_nodes_file_path` | `file_path` | List agents in a file |
| `idx_nodes_parent_id` | `parent_id` | Find children of a node |
| `idx_nodes_node_type` | `node_type` | Filter by type |

**JSON columns**: Five columns store JSON-encoded lists (`caller_ids`, `callee_ids`, `mounted_workspaces`, `extra_tools`, `extra_subscriptions`). These are deserialized by `AgentNode.from_row()` and serialized by `AgentNode.to_row()`.

**Projection updates** (`NodeProjection.apply()`):

| Event | SQL Operation | Fields Updated |
|-------|---------------|----------------|
| `NodeDiscoveredEvent` | UPSERT (INSERT ... ON CONFLICT DO UPDATE) | All identity/source fields, extension fields. **Preserves** `status`, `caller_ids`, `callee_ids`, `last_trigger_event`, `last_completed_at` |
| `NodeRemovedEvent` | DELETE | Removes the row entirely |
| `AgentStartEvent` | UPDATE | `status = 'running'`, `last_trigger_event = event.trigger_event_type` |
| `AgentCompleteEvent` | UPDATE | `status = 'idle'`, `last_completed_at = event.timestamp` |
| `AgentErrorEvent` | UPDATE | `status = 'error'` |

The UPSERT on NodeDiscoveredEvent is carefully designed: it updates source tracking and extension fields but **never overwrites runtime state** (status, last_trigger_event, last_completed_at). This allows re-discovery (e.g., after a file save) without losing the agent's execution state.

**Migration**: `_migrate_routing_fields()` adds `start_byte` and `end_byte` columns to older databases.

### 8.3 subscriptions Table

Persistent storage for agent event subscriptions.

```sql
CREATE TABLE IF NOT EXISTS subscriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id     TEXT NOT NULL,
    pattern_json TEXT NOT NULL,    -- JSON-encoded SubscriptionPattern
    is_default   INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
```

**Indexes:**

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_subscriptions_agent_id` | `agent_id` | Get subscriptions for an agent |
| `idx_subscriptions_is_default` | `is_default` | Distinguish default vs custom subscriptions |

**`pattern_json` format**: JSON-serialized `SubscriptionPattern` (Pydantic `BaseModel`):

```json
{
    "event_types": ["ContentChangedEvent"],
    "from_agents": null,
    "to_agent": null,
    "path_glob": "src/foo.py",
    "tags": null
}
```

All fields are nullable — `null` means "match anything on this dimension."

**In-memory cache**: The `SubscriptionRegistry` maintains `_cache: dict[str, list[tuple[str, SubscriptionPattern]]]` indexed by event type name. The empty string key `""` holds wildcard subscriptions. The cache is rebuilt from the full table on first access (`_rebuild_cache()`) and invalidated to `None` on any mutation.

**Default subscriptions**: When a node is discovered, `register_defaults(agent_id, file_path)` creates two rows:
1. Direct message: `pattern_json = {"to_agent": "<agent_id>", ...}`
2. Source file change: `pattern_json = {"event_types": ["ContentChangedEvent"], "path_glob": "<file_path>", ...}`

### 8.4 edges Table

Stores the graph topology (parent-child and call relationships).

```sql
CREATE TABLE IF NOT EXISTS edges (
    from_id   TEXT NOT NULL,
    to_id     TEXT NOT NULL,
    edge_type TEXT NOT NULL,      -- "parent_of" or "calls"
    PRIMARY KEY (from_id, to_id, edge_type)
);
```

No separate indexes — the composite primary key serves as the index.

**Edge types:**

| Type | Meaning | Example |
|------|---------|---------|
| `parent_of` | Containment (class contains method, file contains function) | `MyClass` → `my_method` |
| `calls` | Call relationship (function calls another) | `process()` → `validate()` |

**Written by**: `RemoraDB.update_edges(nodes)` — iterates over a list of node dicts, inserting `parent_of` edges from `parent_id` and `calls` edges from `callee_ids`. Uses `INSERT OR REPLACE` for idempotency.

**Read by**: `GraphState.read_snapshot()` reads all edges for the graph viewer. `LazyGraph` builds its `rustworkx` graph from these edges for neighborhood traversal.

### 8.5 proposals Table

Stores rewrite proposals awaiting human approval.

```sql
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    old_source  TEXT NOT NULL,    -- Original source code
    new_source  TEXT NOT NULL,    -- Proposed replacement
    diff        TEXT NOT NULL,    -- Unified diff for display
    status      TEXT DEFAULT 'pending',  -- "pending", "accepted", "rejected"
    created_at  REAL NOT NULL,
    file_path   TEXT
);
```

**Lifecycle**: pending → accepted | rejected. Status is updated by `RemoraDB.update_proposal_status()`.

**Access patterns:**
- `store_proposal()` — INSERT with status='pending'
- `get_proposal()` — SELECT by proposal_id
- `get_proposals_for_file()` — SELECT WHERE file_path = ? AND status = 'pending'
- `update_proposal_status()` — UPDATE status

**Used by**: LSP handlers for `remora.acceptProposal` and `remora.rejectProposal` commands. The graph viewer's sidebar shows pending proposals for the selected node.

### 8.6 cursor_focus Table

Single-row table tracking the Neovim cursor position for cross-process communication with the graph viewer.

```sql
CREATE TABLE IF NOT EXISTS cursor_focus (
    id        INTEGER PRIMARY KEY CHECK (id = 1),  -- Only one row ever
    agent_id  TEXT,       -- Node ID nearest to cursor (may be NULL)
    file_path TEXT,       -- File URI
    line      INTEGER,    -- 1-based line number
    timestamp REAL        -- Last update time
);
```

The `CHECK (id = 1)` constraint enforces the single-row invariant. All writes use `INSERT OR REPLACE INTO cursor_focus (id, ...) VALUES (1, ...)`.

**Writers**: `RemoraDB.update_cursor_focus()` (from the `$/remora/cursorMoved` notification handler).

**Readers**: `DBBridge._read_fingerprints()` (reads timestamp for change detection), `GraphState.read_snapshot()` (reads agent_id for node highlighting).

### 8.7 command_queue Table

Asynchronous command dispatch between the web frontend and the LSP server.

```sql
CREATE TABLE IF NOT EXISTS command_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,     -- "chat", "approve", "reject"
    agent_id     TEXT,              -- Target agent (may be NULL)
    payload      JSON NOT NULL,     -- JSON-encoded command data
    status       TEXT DEFAULT 'pending',  -- "pending" or "done"
    created_at   REAL NOT NULL,
    processed_at REAL               -- NULL until processed
);
```

**Writers**: `RemoraDB.push_command()` (sync, immediate commit) and `GraphState.push_command()` (via separate writable connection).

**Readers**: `RemoraDB.poll_commands(limit=10)` — SELECT WHERE status = 'pending' ORDER BY id ASC.

**Completion**: `RemoraDB.mark_command_done(command_id)` — UPDATE SET status = 'done', processed_at = ?.

Commands are never deleted. The `processed_at` column enables audit/replay.

### 8.8 activation_chain Table

Tracks which agents were activated as part of a single causation chain.

```sql
CREATE TABLE IF NOT EXISTS activation_chain (
    correlation_id TEXT NOT NULL,
    agent_id       TEXT NOT NULL,
    depth          INTEGER NOT NULL,    -- Cascade depth
    timestamp      REAL NOT NULL,
    PRIMARY KEY (correlation_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_chain_correlation
ON activation_chain(correlation_id);
```

**Purpose**: Prevents infinite cascade loops. When agent A triggers agent B which triggers agent C, each activation is recorded with the same `correlation_id`. Before triggering, the runner checks `get_activation_chain(correlation_id)` to enforce depth limits and prevent cycles.

**Writers**: `RemoraDB.add_to_chain(correlation_id, agent_id)` — `INSERT OR REPLACE` with depth=1 and current timestamp.

**Readers**: `RemoraDB.get_activation_chain(correlation_id)` — SELECT agent_ids ordered by depth ASC.

---

## 9. Startup & Lifecycle

Remora supports four distinct startup modes: CLI headless, LSP (Neovim), web service, and graph viewer. A fifth "mode" — the standalone chat service — wraps the core kernel factory into a conversation-oriented REST/SSE API. Each mode assembles the same core components (EventStore, SubscriptionRegistry, EventBus, NodeProjection) but wires them differently depending on whether there is an editor connection, an HTTP frontend, or a pure daemon loop.

### 9.1 CLI Headless Mode — `remora swarm start`

**Entry point**: `remora.cli.main:swarm_start` (no `--lsp` flag).

**Source**: `remora/src/remora/cli/main.py:100-165`

#### Bootstrap Sequence

```
remora swarm start [--project-root ROOT] [--config PATH]
│
├── 1. load_config(config_path)            → Config (Pydantic Settings)
├── 2. Resolve project_root (default: cwd)
│
└── asyncio.run(_start()):
    ├── 3. Construct core components:
    │       EventBus()
    │       SubscriptionRegistry(swarm_path / "subscriptions.db")
    │       NodeProjection()
    │       EventStore(
    │           swarm_path / "events" / "events.db",
    │           subscriptions=subscriptions,
    │           event_bus=event_bus,
    │           projection=projection,
    │       )
    │
    ├── 4. await event_store.initialize()
    │   await subscriptions.initialize()
    │   event_store.set_subscriptions(subscriptions)
    │   event_store.set_event_bus(event_bus)
    │
    ├── 5. reconcile_on_startup(root, subscriptions, event_store=event_store)
    │       → Discovers CSTNodes via discover()
    │       → Diffs against EventStore nodes table
    │       → Emits NodeDiscoveredEvent / NodeRemovedEvent / ContentChangedEvent
    │       → Registers default subscriptions for new nodes
    │       → Returns {created, orphaned, updated, total}
    │
    ├── 6. AgentRunner.create_headless(event_store=event_store, ...)
    │       → Constructs _HeadlessServer(event_store)
    │         └── _HeadlessServer.db = _HeadlessDB()  (no-op stubs)
    │       → Returns AgentRunner(server=_HeadlessServer, llm=None, ...)
    │
    ├── 7. runner._running = True
    │
    ├── 8. asyncio.create_task(runner.run_forever())
    │       → Starts command queue polling as a background subtask
    │       → Loops: dequeue Trigger → execute_turn(trigger)
    │
    ├── 9. asyncio.create_task(runner.run_from_event_store(event_store))
    │       → async for (agent_id, event_id, event) in event_store.get_triggers():
    │           runner.trigger(agent_id, correlation_id)
    │       → Bridges EventStore subscription matches into the runner queue
    │
    └── 10. await asyncio.Event().wait()   ← blocks forever (Ctrl+C to stop)
            finally:
              runner.stop()
              cancel runner_task, bridge_task
```

**Key design points**:

- **No LLM in headless mode**: `llm=None` is passed to the runner. If a trigger fires, `execute_turn` emits an error event ("No LLM client configured") rather than crashing. This mode is primarily for testing the subscription/trigger pipeline without actual inference.
- **Two concurrent tasks**: `run_forever()` is the trigger consumer (dequeues and executes), while `run_from_event_store()` is the trigger producer (polls the EventStore for subscription-matched events).
- **`_HeadlessServer` / `_HeadlessDB`**: Minimal duck-type stubs that satisfy the runner's `server.db.*` and `server.event_store` calls. `_HeadlessDB.get_activation_chain()` returns `[]`, `poll_commands()` returns `[]`, etc. — no persistence beyond the EventStore itself.
- **Graceful shutdown**: `asyncio.Event().wait()` keeps the process alive. On `CancelledError` (Ctrl+C), the runner is stopped and both tasks are cancelled with `contextlib.suppress`.

---

### 9.2 LSP Mode — `remora swarm start --lsp`

**Entry point**: `remora.cli.main:swarm_start` (with `--lsp` flag), then hand-off to `remora.lsp.__main__:main`.

**Sources**: `remora/src/remora/cli/main.py:46-98`, `remora/src/remora/lsp/__main__.py:60-248`

#### Phase 1: Pre-Initialization (Synchronous — CLI Process)

```
remora swarm start --lsp [--project-root ROOT]
│
├── 1. load_config(config_path)
│
└── asyncio.run(_prepare_lsp()):
    ├── 2. Construct core components (same as headless):
    │       EventBus, SubscriptionRegistry, NodeProjection, EventStore
    │
    ├── 3. await event_store.initialize()
    │   await subscriptions.initialize()
    │   event_store.set_subscriptions(subscriptions)
    │   event_store.set_event_bus(event_bus)
    │
    ├── 4. reconcile_on_startup(root, subscriptions, event_store=event_store)
    │       → Same diff/emit cycle as headless mode
    │
    └── return (event_store, subscriptions)
```

Reconciliation runs *before* the LSP server starts. This ensures the EventStore nodes table is current before any editor interaction.

#### Phase 2: LSP Server Startup (Handed to pygls Event Loop)

```
lsp_main(event_store=event_store, subscriptions=subscriptions)
│
├── 1. _setup_logging()
│       → stderr handler + timestamped file in .remora/logs/server-YYYY-MM-DD_HHMMSS.log
│       → root logger "remora" at DEBUG, "pygls" at WARNING
│
├── 2. load_config() again (for model settings)
│
├── 3. server = _get_server()        ← imports RemoraLanguageServer singleton
│   server.event_store = event_store
│   server.subscriptions = subscriptions
│
├── 4. LLMClient(base_url, model, api_key)
│       → Wraps structured_agents.client.build_client()
│
├── 5. AgentRunner(server=server, llm=llm)
│   server.runner = runner
│
├── 6. Register INITIALIZED handler:
│       @server.feature(lsp.INITIALIZED)
│       async def _on_initialized(params):
│           asyncio.ensure_future(runner.run_forever())
│           asyncio.ensure_future(_background_scan())
│
└── 7. server.start_io()              ← stdin/stdout LSP transport (blocks)
```

#### Background Scan (`_background_scan`)

Once the editor sends `initialized`, the background scan walks the workspace:

1. **File iteration**: Walks `server.workspace.root_path` recursively, pruning skip-dirs (`__pycache__`, `.venv`, `.git`, `node_modules`, etc.). Accepts `.py`, `.md`, `.toml` files.
2. **Per-file processing**: For each file:
   - Read text content
   - Get existing nodes from EventStore: `event_store.list_nodes(file_path=uri)`
   - Parse with `server.watcher.parse_and_inject_ids(uri, text, old_nodes)`
   - Emit `NodeDiscoveredEvent` for each parsed node (with `source_code`, `source_hash`, `start_byte`, `end_byte`)
   - Emit `NodeRemovedEvent` for nodes in `old_ids - new_ids`
   - Update edges via `server.db.update_edges(nodes)`
3. **Completion**: Calls `server.notify_agents_updated()` to refresh the editor's code lens display.

**Why scan after reconciliation?** Reconciliation runs on `src/` by default (or configured discovery paths) and only checks CST-discoverable symbols. The background scan processes the entire workspace including Markdown and TOML files, and uses the AST watcher's `parse_and_inject_ids()` method which handles incremental ID preservation for nodes that moved within a file.

#### Run-Forever Loop (LSP Context)

`runner.run_forever()` in LSP mode works identically to headless mode — it dequeues `Trigger` objects from the queue and calls `execute_turn()`. The difference is:

- **Triggers come from LSP handlers**, not from `run_from_event_store()`. When the editor sends `textDocument/didChange`, the LSP handler parses the change, emits events to EventStore, and the subscription system matches them to agents, which the server enqueues as triggers via `runner.trigger()`.
- **`server.db` is a real `RemoraDB`** with full persistence (activation chains, proposals, command queue).
- **`server.runner.llm` is a real `LLMClient`** connected to the configured model endpoint.

#### Lifecycle & Shutdown

The LSP server's lifecycle is bound to the editor. When the editor closes the connection, `server.start_io()` returns, the `finally` block in `main()` logs shutdown, and the process exits. There is no explicit cleanup of EventStore/SubscriptionRegistry connections — the process termination handles that.

---

### 9.3 Web Service Mode — `remora serve`

**Entry point**: `remora.cli.main:serve`

**Sources**: `remora/src/remora/cli/main.py:300-317`, `remora/src/remora/service/api.py:32-108`, `remora/src/remora/adapters/starlette.py:18-121`

#### Bootstrap Sequence

```
remora serve [--host 0.0.0.0] [--port 8420] [--project-root ROOT] [--config PATH]
│
├── 1. load_config(config_path)
│
├── 2. RemoraService.create_default(config=config, project_root=root)
│   │
│   ├── resolve project_root (default: cwd)
│   ├── EventBus()
│   ├── SubscriptionRegistry(swarm_root / "subscriptions.db")
│   ├── NodeProjection()
│   ├── EventStore(
│   │       swarm_root / "events" / "events.db",
│   │       subscriptions=subscriptions,
│   │       projection=projection,
│   │   )
│   ├── CairnWorkspaceService(config, swarm_root, project_root)
│   │
│   └── RemoraService.__init__():
│       ├── UiStateProjector()
│       ├── event_bus.subscribe_all(projector.record)
│       │   → Every event on the bus is recorded by the projector
│       ├── ServiceDeps(event_bus, config, project_root, projector,
│       │              event_store, subscriptions, workspace_service)
│       └── _resolve_bundle_default(config)
│
├── 3. create_app(service)             ← Starlette adapter
│   │
│   └── Starlette(routes=[
│           Route("/",              index)           → HTMLResponse(service.index_html())
│           Route("/subscribe",     subscribe)       → DatastarResponse(service.subscribe_stream())
│           Route("/events",        events)          → SSE StreamingResponse
│           Route("/replay",        replay)          → SSE replay from EventStore
│           Route("/input",         submit_input)    → POST: user input
│           Route("/config",        config)          → GET: ConfigSnapshot
│           Route("/snapshot",      snapshot)        → GET: UI state JSON
│           Route("/swarm/agents",  swarm_agents)    → GET: list agents
│           Route("/swarm/agents/{id}", swarm_agent) → GET: single agent
│           Route("/swarm/events",  swarm_events)    → POST: emit event
│           Route("/swarm/subscriptions/{id}", ...)  → GET: agent subscriptions
│       ])
│
└── 4. uvicorn.run(app, host=host, port=port)
```

**Key design points**:

- **No reconciliation**: Unlike headless and LSP modes, `serve` does NOT call `reconcile_on_startup()`. The web service assumes the EventStore was already populated by a prior reconciliation or by a running LSP/headless process. It reads from the same `.remora/` directory.
- **Datastar integration**: The `/subscribe` endpoint returns a `DatastarResponse` that yields Datastar merge fragments. The `UiStateProjector` records every EventBus event and produces a `UiState` snapshot on demand, which `render_dashboard()` converts to HTML components.
- **SSE dual-stream**: `/subscribe` for Datastar UI updates (HTML fragments), `/events` for raw event JSON stream. Both use the same `EventBus.stream()` mechanism.
- **CairnWorkspaceService**: Manages per-agent sandboxed workspaces via the Cairn filesystem abstraction. Used by the workspace-related API endpoints.
- **No AgentRunner**: The web service does not run agents. It provides a UI for monitoring and interacting with a swarm run by a separate headless or LSP process.

#### Lifecycle

Uvicorn manages the HTTP lifecycle. The service runs until the process is killed. EventBus subscriptions and SSE connections are cleaned up by Starlette's ASGI lifecycle.

---

### 9.4 Graph Viewer Startup

**Entry points**: 
- `remora_demo/web/graph/__main__.py` (in remora repo, `python -m remora_demo.web.graph`)
- `frontend/graph/__main__.py` (in remora-demo repo, `python -m graph`)

**Source**: Both files are nearly identical — 71 lines each.

#### Bootstrap Sequence

```
python -m graph --port 8420 --db .remora/indexer.db [--poll-interval 0.3] [-v]
│
├── 1. argparse: --port, --host, --db, --poll-interval, -v
│
├── 2. logging.basicConfig(level=DEBUG if verbose else INFO)
│
├── 3. Warn if db_path does not exist (non-fatal: LSP may create it later)
│
└── asyncio.run(_serve(args)):
    │
    ├── 4. from graph.app import create_app    ← deferred Stario import
    │   (remora repo: from remora_demo.web.graph.app import create_app)
    │
    ├── 5. app, bridge = create_app(db_path=str(args.db), poll_interval=args.poll_interval)
    │   │
    │   ├── GraphState(db_path)            ← SQLite reader (read-only connection)
    │   ├── ForceLayout()                  ← Force-directed layout engine
    │   ├── Relay()                        ← Stario SSE broadcast hub
    │   ├── DBBridge(state, relay, poll_interval)
    │   │   └── Polls DB, diffs snapshots, pushes deltas to Relay
    │   │
    │   └── Stario app with routes:
    │       GET /            → shell view (full HTML page)
    │       GET /subscribe   → SSE event stream via Relay
    │       GET /agent/*     → agent detail sidebar fragment
    │       GET /events      → event list HTML fragment
    │       POST /command    → queue command via push_command()
    │
    ├── 6. asyncio.create_task(bridge.run())
    │       → Starts the polling loop:
    │         while True:
    │           snapshot = state.snapshot()
    │           if snapshot != last_snapshot:
    │             positions = layout.step(snapshot)
    │             relay.broadcast(render(snapshot, positions))
    │           await asyncio.sleep(poll_interval)
    │
    └── 7. await app.serve(host=args.host, port=args.port)
            → Stario HTTP server (blocks)
```

**Key design points**:

- **Deferred Stario import**: `from graph.app import create_app` is inside `_serve()`, not at module top level. This keeps the CLI argument parsing fast and avoids import errors if Stario is not installed (the error surfaces only when `_serve` is called).
- **Read-only DB access** (with one exception): `GraphState` opens the SQLite DB with `PRAGMA query_only=ON` for all read operations. The one exception is `push_command()`, which opens a **separate writable connection** on-demand to insert into the `command_queue` table (see Section 6.2).
- **Two copies, one architecture**: The remora repo's viewer (`remora_demo.web.graph`) and the frontend repo's viewer (`graph`) share nearly identical code. The only material difference is the import path (`remora_demo.web.graph.*` vs `graph.*`) and a column name difference in nodes table queries (`id` vs `node_id`).
- **Tolerant of missing DB**: If the database file doesn't exist at startup, the viewer prints a warning and proceeds. `GraphState.snapshot()` returns an empty snapshot, and the bridge loop waits for the DB to appear (created by the LSP server or headless runner).

#### Lifecycle

The graph viewer runs as a standalone process alongside the LSP or headless runner. It does not coordinate startup with the runner — it simply polls the shared SQLite database. When the process is killed, the Stario server shuts down and the bridge task is cancelled.

---

### 9.5 Chat Service Mode

**Entry points**:
- `python -m remora.service.chat_service` (direct execution, port 8420)
- `create_app()` factory for embedding in a larger Starlette application

**Sources**: `remora/src/remora/service/chat_service.py:1-254`, `remora/src/remora/core/chat.py:1-265`

#### Architecture Overview

The chat service provides a REST + SSE API for single-agent conversations. Unlike the swarm modes (headless, LSP), the chat service creates *ephemeral* `ChatSession` instances rather than running the full subscription/trigger pipeline. Each session wraps a `create_kernel()` call with file-operation tools.

#### Bootstrap Sequence

```
python -m remora.service.chat_service
│
├── 1. ChatServiceState()                ← Module-level singleton
│       .sessions: dict[str, ChatSession]
│       .event_buses: dict[str, EventBus]
│
├── 2. create_app(state=None)            ← Uses module-level singleton
│   │
│   └── Starlette(routes=[
│           POST   /sessions                         → create_session
│           DELETE  /sessions/{session_id}            → delete_session
│           POST   /sessions/{session_id}/messages    → send_message
│           GET    /sessions/{session_id}/history     → get_history
│           GET    /sessions/{session_id}/events      → stream_events (SSE)
│           GET    /tools                             → list_tools
│           GET    /health                            → health check
│       ])
│   │
│   └── on_event("startup"):
│           Logs startup, checks cairn availability
│
└── 3. uvicorn.run(app, host="127.0.0.1", port=8420)
```

#### ChatSession Lifecycle

Each session is created via the `POST /sessions` endpoint:

```
POST /sessions { workspace_path, system_prompt?, tool_presets?, model_name? }
│
├── 1. ChatConfig(workspace_path, system_prompt, tool_presets, model_name)
│       Defaults: system_prompt="You are a helpful assistant."
│                 tool_presets=["file_ops"]
│                 model_name="Qwen/Qwen3-4B"
│                 model_base_url="http://localhost:8000/v1"
│                 max_turns=10
│
├── 2. Validate workspace_path exists and is a directory
│
├── 3. EventBus()                        ← Per-session event bus
│
├── 4. await ChatSession.create(config=config, event_bus=event_bus)
│   │
│   ├── session_id = uuid4()
│   │
│   └── await session._initialize():
│       ├── Config(bundle_root=workspace/.remora, ...)
│       ├── CairnWorkspaceService(config, swarm_root, project_root)
│       ├── await workspace_service.initialize()
│       ├── agent_workspace = await workspace_service.get_agent_workspace(session_id)
│       └── tools = build_chat_tools(agent_workspace, project_root)
│           → read_file, write_file, list_dir, file_exists,
│             search_files, discover_symbols
│           → Each is a Tool.from_function() wrapping AgentWorkspace methods
│
└── 5. Store in state.sessions[session_id] and state.event_buses[session_id]
```

#### Message Processing

Each `POST /sessions/{id}/messages` call runs a complete kernel turn:

```
send_message(content)
│
├── 1. Message.user(content) → append to history
│
├── 2. Build kernel messages:
│       [system_prompt] + [history as KernelMessages]
│
├── 3. create_kernel(
│           model_name, base_url, api_key,
│           tools=self._tools,
│           observer=self.event_bus,    ← EventBus receives ToolCallEvent/ToolResultEvent
│       )
│       → build_client() → ModelAdapter(parser, pipeline) → AgentKernel
│
├── 4. result = await kernel.run(messages, tool_schemas, max_turns=10)
│       → Multi-turn tool loop inside the kernel
│       → ToolCallEvent / ToolResultEvent emitted to EventBus
│
├── 5. await kernel.close()
│
├── 6. Extract tool_calls from result.final_message
│
└── 7. Message.assistant(content, tool_calls) → append to history
       Return AgentResponse(message, turn_count)
```

**Key difference from swarm mode**: The chat service creates a *fresh* `AgentKernel` for each `send()` call and closes it immediately after. There is no persistent runner, no trigger queue, no subscription matching. The kernel factory (`create_kernel()`) handles all the boilerplate: `build_client()` → `ModelAdapter` → `AgentKernel`.

#### SSE Event Streaming

The `GET /sessions/{id}/events` endpoint provides real-time visibility into tool execution:

```python
async with event_bus.stream(ToolCallEvent, ToolResultEvent) as events:
    async for event in events:
        # Yields SSE: event: tool_call / tool_result
        # Data: {name, arguments, timestamp} or {name, output, is_error, timestamp}
```

Each session has its own `EventBus`, so SSE streams are scoped to a single conversation.

#### Tool Presets

The chat service defines tool presets in `DEFAULT_TOOL_PRESETS`:

| Preset | Tools |
|--------|-------|
| `file_ops` | `read_file`, `write_file`, `list_dir`, `file_exists`, `search_files`, `discover_symbols` |
| `all` | Same as `file_ops` (extensible for future presets) |

All tools are built from `AgentWorkspace` methods. `discover_symbols` additionally uses the core `discover()` function to find CST nodes in the workspace.

#### Session Cleanup

`DELETE /sessions/{id}` calls `session.close()`, which calls `workspace_service.close()` to release the Cairn workspace. Both the `ChatSession` and its `EventBus` are removed from `ChatServiceState`.

#### Dependency Injection

`create_app()` accepts an optional `ChatServiceState` parameter for testing. If not provided, it uses the module-level singleton. The state is stored on `application.state.chat_state` for access by Starlette middleware if needed.
