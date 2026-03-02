# Remora — Skills Reference

Condensed mental model for working with Remora (event-driven agent graph workflows) and the graph viewer frontend's data layer.

---

## Table of Contents

1. [What Remora Is](#1-what-remora-is) — Event-driven agent graph workflow framework
2. [Core Data Model](#2-core-data-model) — CSTNode, AgentNode, events, graphs
3. [Event System](#3-event-system) — EventBus, EventStore, EventSourcedBus
4. [Graph Viewer DB Schema](#4-graph-viewer-db-schema) — SQLite tables: nodes, edges, events, cursor_focus, proposals, command_queue
5. [Frontend-Backend Connection](#5-frontend-backend-connection) — GraphState reads SQLite, DBBridge publishes to Relay, SSE pushes to browser
6. [Python Version Split](#6-python-version-split) — Remora needs 3.13, Stario needs 3.14, two processes sharing SQLite
7. [Demo App Architecture](#7-demo-app-architecture) — DESIGN_DOC.md overview: ChatSession, ToolRegistry, ChatService, RemoraClient, DemoState
8. [Key Event Types](#8-key-event-types) — All event types from remora.core.events
9. [Reference Locations](#9-reference-locations) — Where to find full docs and source

---

## 1. What Remora Is

Remora is a framework for composing and running **structured-agent workloads on your code**. Every action flows through a **Pydantic-first event bus**, agents are described via metadata-driven graphs, and every UI consumes the same events.

Key components:
- **Discovery** — scans code for symbols (functions, classes) using tree-sitter, produces `CSTNode` objects
- **Graph** — builds dependency graphs from discovered nodes, determines execution order via topological sort
- **AgentNode** — wraps a `CSTNode` with agent metadata (status, upstream/downstream, bundle mapping)
- **Executor** — walks the graph, runs agents in dependency order, emits events
- **EventBus** — pub/sub for events, drives UIs and persistence
- **EventStore** — SQLite-backed persistent event log

Remora uses **structured-agents** for the LLM kernel (grammar-constrained tool calling) and **Grail** for sandboxed script execution.

---

## 2. Core Data Model

### CSTNode (from discovery)
```python
@dataclass
class CSTNode:
    name: str           # Symbol name (e.g., "calculate_total")
    node_type: str      # "function", "class", "method"
    file_path: Path     # Source file
    start_line: int
    end_line: int
    language: str       # "python", "typescript", etc.
    parent: str | None  # Containing class/module
    # ... additional metadata
```

### AgentNode (graph node)
```python
@dataclass
class AgentNode:
    node: CSTNode
    status: str         # "pending", "running", "completed", "failed"
    upstream: list[str] # Node IDs this depends on
    downstream: list[str] # Node IDs that depend on this
    bundle_path: Path   # Path to agent bundle (YAML config)
```

### Events (frozen dataclasses)
All events are immutable frozen dataclasses with `slots=True`. They flow through the EventBus and are persisted to the EventStore.

---

## 3. Event System

### EventBus
In-memory pub/sub. Handlers subscribe to specific event types.

```python
from remora.core.event_bus import EventBus

bus = EventBus()

# Subscribe
bus.subscribe(GraphStarted, my_handler)

# Publish
bus.publish(GraphStarted(graph_id="abc", node_count=10))
```

### EventStore
SQLite-backed persistent event log. Wraps a raw SQLite connection.

```python
from remora.core.event_store import EventStore

store = EventStore(db_path=".remora/events.db")
store.append(event)
events = store.query(agent_id="xyz")
```

### EventSourcedBus
Combines EventBus + EventStore: every published event is both persisted and broadcast.

---

## 4. Graph Viewer DB Schema

The graph viewer reads from a **shared SQLite database** (`indexer.db`). Remora writes; the frontend reads (WAL mode, `PRAGMA query_only=ON`). The only table the frontend writes to is `command_queue`.

### Tables

**`nodes`** — one row per code symbol being processed
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | Unique node identifier |
| `name` | TEXT | Symbol name |
| `node_type` | TEXT | "function", "class", "method" |
| `status` | TEXT | "pending", "running", "completed", "failed", "orphaned" |
| `file_path` | TEXT | Source file path |
| `start_line` | INT | Start line in file |
| `end_line` | INT | End line in file |
| `language` | TEXT | Programming language |

**`edges`** — relationships between nodes
| Column | Type | Description |
|--------|------|-------------|
| `from_id` | TEXT FK | Source node |
| `to_id` | TEXT FK | Target node |
| `edge_type` | TEXT | "parent_of", "calls" |

**`events`** — event log
| Column | Type | Description |
|--------|------|-------------|
| `event_id` | TEXT PK | Unique event ID |
| `event_type` | TEXT | Event type string |
| `timestamp` | REAL | Unix timestamp |
| `correlation_id` | TEXT | For grouping related events |
| `agent_id` | TEXT | Which agent emitted this |
| `payload` | TEXT | JSON blob with event data |

**`cursor_focus`** — single-row table tracking current editor focus
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | Always 1 |
| `agent_id` | TEXT | Currently focused agent |
| `file_path` | TEXT | Currently focused file |
| `line` | INT | Current line |
| `timestamp` | REAL | When focus changed |

**`proposals`** — agent-generated code proposals
| Column | Type | Description |
|--------|------|-------------|
| `agent_id` | TEXT | Which agent proposed |
| `status` | TEXT | "pending", "accepted", "rejected" |
| `...` | | Additional proposal data |

**`command_queue`** — commands from frontend to backend
| Column | Type | Description |
|--------|------|-------------|
| `command_type` | TEXT | Command name |
| `agent_id` | TEXT | Target agent (nullable) |
| `payload` | TEXT | JSON command data |
| `status` | TEXT | "pending", "processing", "done" |
| `created_at` | REAL | Unix timestamp |

---

## 5. Frontend-Backend Connection

Three layers connect the browser to the database:

```
Browser ←─SSE─→ Stario Handlers ←─Relay─→ DBBridge ←─poll─→ SQLite DB ←─write─→ Remora Backend
```

### GraphState (`graph/state.py`)
- Opens SQLite in **read-only WAL mode** (`PRAGMA query_only=ON`)
- `read_snapshot()` → `GraphSnapshot` (nodes, edges, cursor_focus)
- `read_events_for_agent(agent_id)` → recent events
- `push_command(...)` → writes to `command_queue` (separate writable connection)
- All reads are **synchronous** — handlers call via `asyncio.to_thread()`

### DBBridge (`graph/bridge.py`)
- Polls SQLite for changes using fingerprints (row counts, max timestamps)
- On change, publishes to Relay: `relay.publish("graph.snapshot", snapshot_data)`
- Runs as an asyncio task alongside the Stario server
- `publish()` is sync — safe from the polling loop

### SSE Handler Pattern
```python
async def subscribe_handler(c: Context, w: Writer) -> None:
    # Send initial state
    snapshot = await asyncio.to_thread(state.read_snapshot)
    w.patch(SafeString(render_graph(snapshot)))

    # Stream updates
    async for subject, data in w.alive(relay.subscribe("graph.*")):
        w.patch(SafeString(render_update(data)))
```

---

## 6. Python Version Split

**Remora requires Python 3.13** (vLLM dependency).
**Stario requires Python 3.14** (new language features).

These cannot coexist. The architecture uses **two separate processes**:

```
┌────────────────────────┐     ┌────────────────────────┐
│ Stario Frontend (3.14) │ ←─→ │ Remora Backend (3.13)  │
│ - Web UI, SSE          │HTTP │ - Agent execution       │
│ - Graph viewer         │SQLite│ - Tool calling         │
│ - port 8000            │     │ - port 8420            │
└────────────────────────┘     └────────────────────────┘
```

**Communication paths:**
- **SQLite** (shared file) — for graph viewer (Remora writes, frontend reads)
- **HTTP/SSE** (port 8420) — for chat sessions (frontend calls Remora ChatService)

**Frontend code convention:** Stario is imported only inside `_serve()` in `__main__.py`, never at module top level, so the package remains importable in Python 3.13 (for testing, tooling, etc.).

---

## 7. Demo App Architecture

From `DESIGN_DOC.md`. The demo lets users:
1. Select a workspace directory
2. Configure an agent (system prompt, tool presets)
3. Chat with the agent (inbox/outbox)
4. Watch tool calls and agent state in real-time

### Backend Components (Python 3.13)
- **ChatSession** — wraps structured-agents `AgentKernel` for conversational use
- **ToolRegistry** — dynamic tool selection with presets ("file_ops", "code_analysis")
- **ChatService** — Starlette HTTP service exposing sessions

### Frontend Components (Python 3.14)
- **RemoraClient** — async HTTP client for ChatService (httpx-based)
- **DemoState** — application state dataclass (workspace, session, chat, tool log)
- **Views** — HTML rendering functions (plain strings, no Stario dependency)
- **Handlers** — Stario handler factories (Go-style DI via closures)

### API Endpoints (port 8420)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /sessions` | Create | New chat session |
| `DELETE /sessions/{id}` | Delete | End session |
| `POST /sessions/{id}/messages` | Create | Send message, get response |
| `GET /sessions/{id}/events` | SSE | Stream tool events |
| `GET /tools` | Read | List tool presets |
| `GET /health` | Read | Health check |

---

## 8. Key Event Types

From `remora.core.events`:

### Graph lifecycle
- `GraphStarted(graph_id, node_count, timestamp)`
- `GraphCompleted(graph_id, results, duration, timestamp)`
- `GraphFailed(graph_id, error, timestamp)`

### Agent lifecycle
- `AgentStarted(agent_id, node_name, bundle_path, timestamp)`
- `AgentCompleted(agent_id, result, duration, timestamp)`
- `AgentFailed(agent_id, error, timestamp)`

### Re-exported from structured-agents
- `ToolCallEvent(tool_name, arguments, timestamp)`
- `ToolResultEvent(tool_name, output_preview, is_error, timestamp)`
- `TurnStartEvent`, `TurnEndEvent`
- `KernelStartEvent`, `KernelEndEvent`

### Human interaction
- `HumanInputRequested(agent_id, prompt, timestamp)`
- `HumanInputReceived(agent_id, input_text, timestamp)`
- `HumanApprovalRequested(agent_id, proposal_id, timestamp)`
- `HumanApprovalReceived(agent_id, proposal_id, approved, timestamp)`

### Checkpoint
- `CheckpointSaved(graph_id, checkpoint_id, timestamp)`
- `CheckpointRestored(graph_id, checkpoint_id, timestamp)`

---

## 9. Reference Locations

| Resource | Path |
|----------|------|
| Remora source + docs | `.context/remora_v0.4.10/` |
| Remora usage guide | `.context/remora_v0.4.10/HOW_TO_USE_REMORA.md` |
| Remora events source | `.context/remora_v0.4.10/src/remora/core/events.py` |
| Remora event store | `.context/remora_v0.4.10/src/remora/core/event_store.py` |
| Remora graph builder | `.context/remora_v0.4.10/src/remora/core/graph.py` |
| structured-agents docs | `.context/structured-agents_v0.3.4/` |
| Grail docs | `.context/grail_v3.0.0/` |
| Design document | `DESIGN_DOC.md` |
| Nvim demo concept | `NVIM_DEMO_CONCEPT.md` |
| Graph viewer source | `frontend/graph/` |
| Graph viewer state | `frontend/graph/state.py` |
| Graph viewer bridge | `frontend/graph/bridge.py` |

---
