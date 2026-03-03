# Remora Architecture Overview

> A streamlined guide to the Remora system. For implementation details, code-level APIs, and full SQL schemas, see [DEMO_ARCHITECTURE.md](./DEMO_ARCHITECTURE.md).

---

## 1. What Is Remora?

Remora is an **event-sourced, reactive agent system** that treats every function, class, and file in a codebase as an autonomous agent. All state lives in a **single SQLite database** (`.remora/indexer.db`) shared between components via WAL mode.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REMORA CORE                                      │
│                                                                             │
│  Discovery (tree-sitter)  │  Events (frozen Pydantic)  │  Subscriptions    │
│  AgentNode (model+prompt) │  EventStore (unified DB)   │  Projections      │
│  AgentContext (callbacks)  │  EventBus (in-process)     │  Kernel Factory   │
│  Workspace + Cairn        │  Extensions (.remora/)     │  Swarm Tools (5)  │
└─────────────────────────────────────────────────────────────────────────────┘
        │ SQLite WAL              │ SQLite WAL                    │ In-process
        ▼                         ▼                               ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────────┐
│  NEOVIM DEMO    │   │  GRAPH VIEWER   │   │  WEB SERVICE DEMO           │
│  (LSP Server)   │   │  (Stario App)   │   │  (Starlette + Datastar)     │
│                 │   │                 │   │                             │
│  AgentRunner    │   │  GraphState     │   │  RemoraService              │
│  ASTWatcher     │   │  DBBridge       │   │  UiStateProjector           │
│  LazyGraph      │   │  ForceLayout    │   │  ChatService                │
│  RemoraDB       │   │  SVG Rendering  │   │  Component System           │
│  Mock LLM       │   │  Datastar SSE   │   │  Datastar SSE               │
└─────┬───────────┘   └────────┬────────┘   └────────────┬────────────────┘
      │ LSP JSON-RPC           │ HTTP + SSE               │ HTTP + SSE
      ▼                        ▼                          ▼
   Neovim Editor            Browser                    Browser / API Client
```

### Repositories

| Repository | Path | Contents |
|------------|------|----------|
| **Remora** (library) | `/remora/src/remora/` | Core engine, LSP server, service layer, UI system, CLI |
| **remora_demo** | `/remora/remora_demo/` | Neovim demo: mock LLM, launch script, demo project, web graph viewer |
| **Frontend** | `/remora-demo/frontend/` | Graph viewer (copy), mock LLM, 179 tests |

---

## 2. Core Concepts

### Events

All events are **frozen Pydantic models** — immutable and hashable. Four categories:

| Category | Examples | Purpose |
|----------|---------|---------|
| Agent lifecycle | `AgentStartEvent`, `AgentCompleteEvent`, `AgentErrorEvent` | Track execution status |
| Human-in-the-loop | `HumanInputRequestEvent`, `HumanInputResponseEvent` | Agent blocks for human input |
| Reactive swarm | `AgentMessageEvent`, `FileSavedEvent`, `ContentChangedEvent`, `ManualTriggerEvent` | Subscription-routed triggers |
| Node lifecycle | `NodeDiscoveredEvent`, `NodeRemovedEvent` | Drive the `nodes` table projection |

Plus 7 re-exported kernel events (`ToolCallEvent`, `ModelRequestEvent`, etc.) — 18 event types total via the `RemoraEvent` union.

### Discovery

Tree-sitter parses source files into **CSTNode** objects (frozen Pydantic models). Each node gets a deterministic ID: `SHA256("file_path:name:start_line:end_line")[:16]`. Custom `__hash__` hashes by `node_id` only, so a node with changed source text but the same position hashes equally — intentional for reconciliation diffs.

### AgentNode

A single Pydantic model that serves **three roles**:
1. **Database row** — `to_row()` / `from_row()` serialize list fields as JSON
2. **LLM prompt** — `to_system_prompt()` builds a multi-section Markdown identity prompt
3. **LSP protocol** — `to_code_lens()`, `to_hover()`, `to_code_actions()` produce lsprotocol types

Field groups: identity (from CSTNode), graph context (parent, callers, callees), runtime state (status, last trigger), specialization (from extension config matching).

### Subscriptions

**SubscriptionPattern** (Pydantic model) with optional fields: `event_types`, `from_agents`, `to_agent`, `path_glob`, `tags`. A `None` field means "match anything"; all non-None fields must match (AND). The **SubscriptionRegistry** maintains an in-memory cache indexed by event type, rebuilt from SQLite on demand and invalidated on mutation.

Every discovered node gets two default subscriptions:
- Direct message: `to_agent = <agent_id>`
- Source file change: `event_types = ["ContentChangedEvent"], path_glob = <file_path>`

### Projections

**NodeProjection** materializes events into the `nodes` table in the same transaction as `EventStore.append()`. `NodeDiscoveredEvent` → UPSERT (preserving runtime state), `NodeRemovedEvent` → DELETE, status events → UPDATE status field. Extension configs are matched during projection.

### AgentContext

Typed Pydantic model replacing the old `externals: dict`. Carries async callbacks (`emit_event`, `register_subscription`, `broadcast`, `query_agents`) plus Cairn filesystem externals. Built per-turn by the runner. `as_externals()` merges everything into a flat dict for Grail backward compatibility.

### Swarm Tools

5 structured tools available to agents: `send_message`, `subscribe`, `unsubscribe`, `broadcast`, `query_agents`. All operate through AgentContext callbacks. Grail tools (`.pym` scripts) are discovered dynamically from bundle directories.

---

## 3. Data Flow Pipeline

End-to-end trace from source code to agent activity:

```
Source File
    │
    ▼  tree-sitter parsing
CSTNode (frozen Pydantic model)
    │
    ▼  NodeDiscoveredEvent
EventStore.append()
    │  ├── INSERT into events table
    │  ├── NodeProjection UPSERT into nodes table  ← same transaction
    │  └── COMMIT
    │
    ▼  post-commit
SubscriptionRegistry.get_matching_agents(event)
    │  ├── cache lookup by event_type
    │  ├── pattern.matches(event) for each candidate
    │  └── deduplicate by agent_id
    │
    ▼  push to trigger queue
AgentRunner.execute_turn()
    │  ├── Load AgentNode from nodes table
    │  ├── Emit AgentStartEvent → status = "running"
    │  ├── Build system prompt + user messages
    │  ├── Multi-round LLM tool loop (max 5 rounds)
    │  └── Emit AgentCompleteEvent → status = "idle"
    │
    ▼  tool side-effects (e.g. send_message → AgentMessageEvent)
Re-enters pipeline at subscription matching ← cascade
```

**Cascade prevention:** max trigger depth (10), per-agent cooldown (1000ms), concurrency semaphore (4), DB-backed activation chain with cycle detection.

**Reconciliation at startup:** Diffs discovered CSTNodes against existing `nodes` table. Emits `NodeDiscoveredEvent` for new/changed nodes, `NodeRemovedEvent` for deleted ones, registers default subscriptions.

---

## 4. The Database

All state lives in `.remora/indexer.db` — one file, 8 tables, WAL mode for concurrent access.

| Table | Purpose | Key Detail |
|-------|---------|------------|
| `events` | Append-only event log | Routing columns (`from_agent`, `to_agent`, `correlation_id`, `tags`) denormalized for indexed queries. Never updated. |
| `nodes` | Materialized agent state | Maintained by NodeProjection. UPSERT preserves runtime state across re-discovery. 5 JSON-encoded list columns. |
| `subscriptions` | Event routing patterns | `pattern_json` stores serialized SubscriptionPattern. In-memory cache in SubscriptionRegistry. |
| `edges` | Graph topology | `parent_of` and `calls` edge types. Composite PK `(from_id, to_id, edge_type)`. |
| `proposals` | Rewrite proposals | Status: pending → accepted \| rejected. |
| `cursor_focus` | Neovim cursor position | Single-row table (`CHECK id = 1`). Bridges editor cursor to graph viewer highlight. |
| `command_queue` | Web → LSP commands | Async command channel. Status: pending → done. Never deleted (audit trail). |
| `activation_chain` | Cascade tracking | Records `(correlation_id, agent_id, depth)` to prevent infinite loops. |

**Sharing model:** EventStore owns the connection. SubscriptionRegistry and RemoraDB share it in "shared mode" to avoid multiple connections. GraphState opens a separate read-only connection (`PRAGMA query_only=ON`).

---

## 5. Modes of Operation

### LSP Mode (Neovim Demo) — `remora swarm start --lsp`

The main demo. Runs as a single process: LSP server + AgentRunner + background workspace scan.

1. Reconciliation runs first (before editor connects)
2. LSP server starts on stdin/stdout (pygls)
3. Background scan walks workspace, parsing files with ASTWatcher
4. AgentRunner consumes trigger queue, executes turns via LLM
5. Agents propose rewrites → appear as diagnostics in Neovim → human accepts/rejects

**Key LSP components:**
- **AgentRunner** — Trigger queue → execute_turn → multi-round tool loop. Handles cooldown, depth limits, cascade prevention.
- **ASTWatcher** — Tree-sitter file parsing, incremental ID preservation, `# rm_xxxxxxxx` tag injection.
- **RemoraDB** — LSP-specific tables (proposals, edges, activation_chain, cursor_focus, command_queue).
- **LazyGraph** — rustworkx graph with lazy 2-hop neighborhood loading via recursive CTE.
- **RewriteProposal** — Agent's proposed code change → WorkspaceEdit + Diagnostic + CodeActions.

**3 built-in agent tools:** `rewrite_self` (propose code change), `message_node` (inter-agent messaging), `read_node` (read another agent's source).

**8 LSP commands:** getAgentPanel, chat, requestRewrite, executeTool, acceptProposal, rejectProposal, selectAgent, messageNode.

**4 custom notifications:** `$/remora/cursorMoved`, `$/remora/submitInput` (client → server), `$/remora/event`, `$/remora/agentsUpdated` (server → client).

### CLI Headless Mode — `remora swarm start`

Same pipeline without an editor. `AgentRunner.create_headless()` uses stub DB objects. Primarily for testing the subscription/trigger pipeline. `llm=None` by default — triggers emit error events rather than crashing.

### Web Service Mode — `remora serve`

Starlette + Datastar dashboard for monitoring. Does **not** run agents or reconcile — reads from a DB populated by another process. Provides REST endpoints for agent listing, event streaming (SSE), and human input. UiStateProjector reduces events into dashboard state.

### Graph Viewer — `python -m graph`

Standalone Stario process that reads the shared DB and renders a real-time force-directed SVG graph in the browser.

**How it works:**
1. **GraphState** reads the DB (read-only, WAL mode)
2. **DBBridge** polls every 300ms using lightweight fingerprints (`count(*), max(rowid)` per table)
3. When a fingerprint changes → publishes to Stario **Relay** → SSE handler sends Datastar patches
4. **ForceLayout** computes server-side positions (repulsion, attraction, gravity, damping)
5. **SVG rendering** produces node circles + edge lines with Catppuccin Mocha colors
6. CSS transitions (0.5s ease-out) animate position changes in the browser

**Two copies exist** — `frontend/graph/` and `remora_demo/web/graph/` — identical except for import paths and a column name difference (`node_id` vs `id`). Both normalize to `remora_id` internally.

### Chat Service — standalone Starlette app

Ephemeral chat sessions wrapping `AgentKernel` with file-operation tools. REST + SSE API for single-agent conversations. No trigger queue or subscriptions — creates a fresh kernel per `send()` call.

---

## 6. Key Boundaries

These are the interfaces where data changes shape between subsystems.

### Event Serialization

Events go through: **Pydantic model** → `model_dump()` → **dict** → `json.dumps()` → **SQLite TEXT**. Three-tier fallback for non-Pydantic events (dataclass → `asdict()`, plain object → `vars()`). Events come back as **plain dicts**, not typed models — the read side only needs the data.

### EventStore → Subscriptions → Trigger Queue

After `append()` commits: query matching agents → push `(agent_id, event_id, event)` to `asyncio.Queue`. This happens **outside** the transaction so it never blocks writes.

### AgentNode Triple Interface

One model, three protocols:
- **SQLite**: `to_row()` JSON-encodes list fields via `model_dump()`, `from_row()` parses them back
- **LLM**: `to_system_prompt()` builds identity/source/graph-context/rules Markdown
- **LSP**: `to_code_lens()`, `to_hover()`, `to_code_actions()` produce lsprotocol types (deferred import)

### SQLite as Shared State Bus

Multiple processes share one DB file via WAL mode. The LSP server and web service read/write; the graph viewer is read-only (except `push_command()` via a separate writable connection). No distributed transactions — each process sees a snapshot-consistent view. The graph viewer's 300ms polling interval means up to 300ms of lag, which is imperceptible.

### command_queue (Web → LSP)

The graph viewer's `/command` endpoint inserts into `command_queue`. The AgentRunner polls for pending commands and dispatches them (chat, approve, reject). This is the only write path from the graph viewer to the main database.

### cursor_focus (Neovim → Graph Viewer)

`$/remora/cursorMoved` → find agent at position → write to single-row `cursor_focus` table → DBBridge detects timestamp change → graph viewer highlights the focused node with a glow filter.

---

## 7. Mock LLM (Demo Mode)

`MockLLMClient` provides deterministic, scripted responses for the demo. Messages are parsed into a `MockContext` (agent name/type, trigger type, round number), then matched against a priority-ordered script list.

**Golden path demo flow:**
1. User edits `load_config` → adds parameter
2. `ContentChangedEvent` triggers the agent
3. Agent analyzes change, sends `message_node("test_load_yaml", "update for...")`
4. Test agent reads the source via `read_node("load_config")`
5. Test agent calls `rewrite_self(updated_test_code)`
6. Proposal appears as diagnostic in Neovim → user accepts or rejects

---

## 8. Extension System

Extensions customize agents via Python classes in `.remora/models/`. Each has `matches(node_type, name, file_path, source_code) → bool` and `get_extension_data() → dict` (overrides for `custom_system_prompt`, `mounted_workspaces`, `extra_tools`, `extra_subscriptions`). Files loaded alphabetically — first match wins. Mtime-based caching at module level skips reload if no files changed.
