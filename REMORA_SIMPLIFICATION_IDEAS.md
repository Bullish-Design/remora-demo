# Remora Unification & Simplification Analysis

## Executive Summary

This document analyzes how to **unify three concepts** into one simple, elegant library:

1. **Remora** (existing) - Graph execution with workspaces, events, tools
2. **CST Agent Swarm** - Persistent agents with message passing
3. **Neovim Integration** - Editor as swarm UI

The goal is a **single mental model** that's easy to reason about while retaining all necessary functionality.

**Key Insight**: Much of what Remora already has is *exactly what we need* for the swarm - we just need to reframe it, not remove it.

---

## Part 1: The Unified Mental Model

### Current Remora Mental Model

```
Discovery → Graph → Executor → Results
              ↓
         (batch execution, then done)
```

### Unified Mental Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     UNIFIED REMORA                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AGENTS = CST Nodes with persistent state                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Agent                                                   │    │
│  │  ├── identity (node_id, type, path, parent)             │    │
│  │  ├── workspace (Cairn .db file)                         │    │
│  │  ├── state (connections, chat_history) → state.jsonl    │    │
│  │  ├── inbox ← EventStore queries                         │    │
│  │  └── outbox → EventStore appends                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  EXECUTION = Turn-based, on-demand                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Triggers:                    │  Agent Turn:            │    │
│  │  • File change                │  1. Load state          │    │
│  │  • Message received           │  2. Read inbox          │    │
│  │  • User chat (Neovim)         │  3. Run kernel          │    │
│  │  • Manual trigger             │  4. Write outbox        │    │
│  │                               │  5. Save state          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  COMMUNICATION = EventStore (already SQLite!)                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  EventStore.append(AgentMessage)  → outbox              │    │
│  │  EventStore.replay(to_agent=X)    → inbox               │    │
│  │  EventStore.replay(type=*)        → UI updates          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The "Aha!" Realizations

1. **EventStore IS the message bus** - We don't need a new system. Just add `from_agent`, `to_agent` columns.

2. **Workspaces ARE agent state** - Cairn already provides persistent, isolated workspaces per agent.

3. **GraphExecutor can run single agents** - It already handles one agent at a time internally.

4. **Events already flow to UI** - The projector pattern works for both batch execution AND swarm visualization.

5. **Discovery already maps CST → Agents** - We just need to persist the mapping.

---

## Part 2: What Remora Already Has (And We Need)

### 2.1 EventStore - THE MESSAGE BUS

**Location**: `core/event_store.py`

**What it does**:
- SQLite-backed event persistence
- Indexed queries by `graph_id`, `event_type`, `timestamp`
- Replay with filtering (`since`, `until`, `after_id`)

**Why we NEED it for swarm**:
- Agent messages are just events with routing
- Inbox = `replay(to_agent=X, since_id=last_seen)`
- Outbox = `append(AgentMessageEvent)`
- Already handles concurrency (async locks)

**Modification needed**: Add routing columns
```sql
ALTER TABLE events ADD COLUMN from_agent TEXT;
ALTER TABLE events ADD COLUMN to_agent TEXT;
ALTER TABLE events ADD COLUMN correlation_id TEXT;

CREATE INDEX idx_events_to_agent ON events(to_agent);
```

**Verdict**: **KEEP and EXTEND** (~30 lines to add)

---

### 2.2 EventBus - INTERNAL COORDINATION

**Location**: `core/event_bus.py`

**What it does**:
- In-memory pub/sub for live events
- Type-based subscription
- Async streaming for UI

**Why we NEED it for swarm**:
- Live notifications to Neovim ("agent has new inbox message")
- UI updates during agent turns
- Decouples components

**Verdict**: **KEEP AS-IS** (already simple enough)

---

### 2.3 Discovery - CST → AGENT MAPPING

**Location**: `core/discovery.py`

**What it does**:
- Tree-sitter parsing
- `CSTNode` with `node_id`, `node_type`, `file_path`, `start_line`, `end_line`
- Deterministic ID generation

**Why we NEED it for swarm**:
- Maps code constructs to agents
- IDs are stable across restarts
- Multi-language support

**Verdict**: **KEEP AS-IS** (core value)

---

### 2.4 Workspaces - AGENT ISOLATION

**Location**: `core/workspace.py`, `core/cairn_bridge.py`

**What it does**:
- Per-agent `.db` files via Cairn
- CoW semantics
- Read/write isolation

**Why we NEED it for swarm**:
- Each agent has isolated workspace
- Content modifications don't conflict
- Already persistent!

**Modification needed**:
- Add `state.jsonl` alongside `workspace.db` for agent metadata

**Verdict**: **KEEP and EXTEND**

---

### 2.5 Executor - AGENT TURN RUNNER

**Location**: `core/executor.py`

**What it does**:
- Runs agent kernels with tools
- Handles concurrency, timeouts, errors
- Emits lifecycle events

**Why we NEED it for swarm**:
- Core execution logic is reusable
- Already integrates with workspaces, tools, events

**Modification needed**:
- Extract single-agent execution as `run_turn(agent_id, trigger)`
- Keep graph execution for batch mode

**Verdict**: **KEEP and REFACTOR** (extract `AgentRunner`)

---

### 2.6 Graph - AGENT TOPOLOGY

**Location**: `core/graph.py`

**What it does**:
- `AgentNode` with `upstream`/`downstream` relationships
- Topological sorting
- Batch computation

**Why we NEED it for swarm**:
- Agents have parent/child relationships
- Message routing uses topology
- Batch execution still useful

**Verdict**: **KEEP AS-IS**

---

### 2.7 Context Builder - PROMPT ENRICHMENT

**Location**: `core/context.py`

**What it does**:
- Builds context from recent events
- Two-track memory (recent + long-term)

**Assessment**: The two-track pattern IS useful for agents that need to remember things. However, it's currently tied to graph execution events.

**Modification needed**:
- Generalize to work with agent message history
- Simplify the "long track" to just be agent's `connections` dict

**Verdict**: **SIMPLIFY** (merge into agent state)

---

## Part 3: What Can Actually Be Removed

### 3.1 DI Container

**Location**: `core/container.py` (~150 LOC)

**Current purpose**: Wire up dependencies for graph execution.

**Why remove**:
- For a personal project, explicit wiring is clearer
- Container adds indirection without proportional benefit
- Swarm mode needs different initialization anyway

**Replacement**:
```python
# In service/api.py or a new swarm/runtime.py
def create_swarm(config_path: Path) -> SwarmRuntime:
    config = Config.from_yaml(config_path)
    event_store = EventStore(config.workspace_path / "events.db")
    event_bus = EventBus()
    # ... explicit, readable wiring
```

**Verdict**: **REMOVE** (~150 LOC saved)

---

### 3.2 Checkpoint System

**Location**: `core/checkpoint.py` (~170 LOC)

**Current purpose**: Save/restore graph execution state.

**Why remove**:
- Swarm agents have persistent state by design (state.jsonl)
- Graph execution checkpoints are separate from agent persistence
- For personal use, "rerun if it fails" is fine

**What replaces it**: Agent state persistence (simpler, per-agent)

**Verdict**: **REMOVE** (~170 LOC saved)

---

### 3.3 Indexer Subsystem

**Location**: `indexer/` (~300 LOC)

**Current purpose**: Background code indexing daemon.

**Why remove**:
- Never completed or integrated
- Discovery already does what we need
- Swarm agents ARE the "index"

**Verdict**: **REMOVE** (~300 LOC saved)

---

### 3.4 Tool Registry Abstraction

**Location**: `core/tool_registry.py` (~120 LOC)

**Current purpose**: Dynamic tool registration with presets.

**Why simplify**:
- Tools don't change at runtime
- Presets rarely used
- Direct imports are clearer

**Replacement**:
```python
# In core/tools/grail.py
def get_tools_for_agent(agent_type: str, externals: dict) -> list[Tool]:
    base_tools = [ReadFileTool(externals), WriteFileTool(externals), ...]
    if agent_type == "function":
        return base_tools + [SendMessageTool(), ...]
    return base_tools
```

**Verdict**: **SIMPLIFY** (~80 LOC saved)

---

### 3.5 Streaming Sync Manager

**Location**: `core/streaming_sync.py` (~150 LOC)

**Current purpose**: Lazy file syncing with batching.

**Assessment**: Only needed for `SyncMode.LAZY`. For personal use on local files, `SyncMode.FULL` is fine and much simpler.

**Verdict**: **REMOVE** if only using FULL sync (~150 LOC saved)

---

### 3.6 Dead Code

| Item | Location | LOC |
|------|----------|-----|
| `WorkspaceManager` class | `workspace.py` | ~50 |
| `EventBridge` class | `event_bus.py` | ~30 |
| Workspace snapshot stubs | `workspace.py` | ~20 |

**Verdict**: **REMOVE** (~100 LOC saved)

---

## Part 4: What Needs to Be Added

### 4.1 Agent State Persistence

**New file**: `core/agent_state.py` (~100 LOC)

```python
@dataclass
class AgentState:
    """Persistent state for a swarm agent."""
    identity: AgentIdentity
    connections: dict[str, str]    # symbolic_name -> agent_id
    chat_history: list[Message]
    last_content_hash: str
    last_activated: float
    last_seen_event_id: int

    @classmethod
    def load(cls, path: Path) -> "AgentState": ...
    def save(self, path: Path) -> None: ...
```

### 4.2 Swarm State Registry

**New file**: `core/swarm_state.py` (~100 LOC)

```python
class SwarmState:
    """Registry of all agents in the swarm."""

    async def register_agent(self, agent_id: str, metadata: AgentMetadata) -> None
    async def get_agent(self, agent_id: str) -> AgentMetadata | None
    async def list_agents(self, parent_id: str | None = None) -> list[AgentMetadata]
    async def list_agents_for_file(self, path: Path) -> list[AgentMetadata]
```

### 4.3 Agent Runner (Refactored from Executor)

**New file**: `core/agent_runner.py` (~150 LOC)

```python
class AgentRunner:
    """Runs a single agent turn."""

    async def run_turn(self, agent_id: str, trigger: TriggerEvent) -> TurnResult:
        # 1. Load agent state
        # 2. Read inbox from EventStore
        # 3. Build prompt
        # 4. Run kernel (reuse from executor)
        # 5. Process outbox
        # 6. Save state
```

### 4.4 Startup Reconciler

**New file**: `core/reconciler.py` (~100 LOC)

```python
async def reconcile(project_path: Path, swarm_state: SwarmState) -> ReconcileResult:
    """Diff current CST against saved agents, spawn/update/orphan as needed."""
    current_nodes = discover(project_path)
    saved_agents = await swarm_state.list_agents()
    # ... diff and reconcile
```

### 4.5 EventStore Extension

**Modify**: `core/event_store.py` (~50 LOC added)

```python
# Add to EventStore class
async def get_inbox(
    self,
    agent_id: str,
    *,
    since_id: int | None = None,
) -> AsyncIterator[dict]:
    """Get messages addressed to an agent."""

async def get_inbox_count(self, agent_id: str) -> int:
    """Count unread messages for an agent."""
```

### 4.6 Agent Message Event

**Modify**: `core/events.py` (~20 LOC added)

```python
@dataclass(frozen=True)
class AgentMessageEvent:
    """Message between agents (via EventStore)."""
    from_agent: str
    to_agent: str
    action: str  # "request", "response", "notify"
    content: dict[str, Any]
    correlation_id: str | None = None
    timestamp: float = field(default_factory=time.time)
```

### 4.7 Neovim RPC Server

**New file**: `nvim/server.py` (~200 LOC)

```python
class NvimRpcServer:
    """JSON-RPC server for Neovim plugin."""

    async def _select_agent(self, params) -> dict
    async def _chat_with_agent(self, params) -> dict
    async def _trigger_agent(self, params) -> dict
    async def _buffer_changed(self, params) -> dict
```

---

## Part 5: The Unified Architecture

### File Structure

```
remora/
├── core/
│   ├── __init__.py
│   ├── config.py             # SIMPLIFY: Flatten to ~100 LOC
│   ├── discovery.py          # KEEP: ~250 LOC
│   ├── graph.py              # KEEP: ~150 LOC
│   ├── executor.py           # KEEP: For batch mode, ~300 LOC
│   ├── agent_runner.py       # NEW: Single-agent turns, ~150 LOC
│   ├── agent_state.py        # NEW: Persistent agent state, ~100 LOC
│   ├── swarm_state.py        # NEW: Agent registry, ~100 LOC
│   ├── reconciler.py         # NEW: Startup diff, ~100 LOC
│   ├── events.py             # EXTEND: +AgentMessageEvent, ~150 LOC
│   ├── event_bus.py          # KEEP: ~120 LOC
│   ├── event_store.py        # EXTEND: +inbox queries, ~300 LOC
│   ├── workspace.py          # SIMPLIFY: AgentWorkspace only, ~100 LOC
│   ├── cairn_bridge.py       # KEEP: ~200 LOC
│   ├── cairn_externals.py    # KEEP: ~70 LOC
│   └── tools/
│       └── grail.py          # EXTEND: +messaging tools, ~250 LOC
│
├── nvim/                     # NEW
│   ├── __init__.py
│   └── server.py             # Neovim RPC, ~200 LOC
│
├── service/
│   ├── api.py                # SIMPLIFY: ~100 LOC
│   └── handlers.py           # KEEP: ~150 LOC
│
├── adapters/
│   └── starlette.py          # EXTEND: +swarm routes, ~150 LOC
│
├── ui/
│   ├── projector.py          # KEEP: ~150 LOC
│   ├── view.py               # KEEP: ~50 LOC
│   └── components/           # KEEP: ~300 LOC
│
├── cli/
│   └── main.py               # EXTEND: +swarm commands, ~150 LOC
│
└── utils/                    # KEEP: ~110 LOC

REMOVED:
├── core/container.py         # -150 LOC (DI container)
├── core/checkpoint.py        # -170 LOC (checkpointing)
├── core/context.py           # -170 LOC (merged into agent_state)
├── core/tool_registry.py     # -120 LOC (simplified)
├── core/streaming_sync.py    # -150 LOC (not needed for FULL sync)
└── indexer/                  # -300 LOC (dead code)
```

### Line Count Summary

| Category | Removed | Added | Net |
|----------|---------|-------|-----|
| Dead code (indexer, stubs) | -400 | - | -400 |
| DI Container | -150 | - | -150 |
| Checkpoint | -170 | - | -170 |
| Context → Agent State | -170 | +100 | -70 |
| Tool Registry → Direct | -120 | +30 | -90 |
| Streaming Sync | -150 | - | -150 |
| Swarm additions | - | +550 | +550 |
| Neovim server | - | +200 | +200 |
| **Total** | **-1160** | **+880** | **-280** |

**Result**: Slightly smaller codebase that does MORE.

---

## Part 6: The Simple Mental Model

### One Sentence

> **Remora treats every code construct as a persistent agent with an inbox, and uses SQLite events for both message passing and UI updates.**

### The Core Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│   STARTUP                                                        │
│   ───────                                                        │
│   1. Load config                                                │
│   2. Discover CST nodes (tree-sitter)                           │
│   3. Reconcile: diff vs saved agents, spawn/update/orphan       │
│   4. Start Neovim RPC server (optional)                         │
│                                                                  │
│   AGENT TURN (triggered by file change / message / user chat)   │
│   ──────────                                                     │
│   1. Load agent state from state.jsonl                          │
│   2. Query inbox from EventStore                                │
│   3. Build prompt (code content + inbox + chat history)         │
│   4. Run kernel with tools                                      │
│   5. Append outgoing messages to EventStore                     │
│   6. Save agent state                                           │
│   7. Emit events for UI                                         │
│                                                                  │
│   COMMUNICATION                                                  │
│   ─────────────                                                  │
│   • Agent A sends message: EventStore.append(to_agent=B)        │
│   • Agent B reads inbox: EventStore.replay(to_agent=B)          │
│   • Neovim sees update: EventBus subscription                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Equations

```
Agent = CSTNode + Workspace + State + Inbox + Outbox

Inbox = EventStore.replay(to_agent=self.id, since_id=last_seen)

Outbox = EventStore.append(AgentMessageEvent(from_agent=self.id, ...))

Turn = Load → Inbox → Kernel → Outbox → Save

Swarm = Agents + EventStore + Triggers
```

---

## Part 7: Configuration Simplification

### Current (6 nested classes)

```python
RemoraConfig
├── DiscoveryConfig
├── BundleConfig
├── ExecutionConfig
├── IndexerConfig      # Remove (unused)
├── WorkspaceConfig
└── ModelConfig
```

### Simplified (1 flat class)

```python
@dataclass
class Config:
    # Project
    project_path: Path = Path.cwd()
    languages: list[str] = field(default_factory=lambda: ["python"])

    # Execution
    max_concurrency: int = 4
    timeout: int = 120

    # Model
    model_url: str = "http://localhost:8000/v1"
    model_name: str = "Qwen/Qwen3-4B"
    api_key: str = "EMPTY"

    # Swarm
    swarm_path: Path = field(default_factory=lambda: Path.home() / ".cache/remora")

    # Neovim
    nvim_socket: str = "/tmp/remora.sock"

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        data = yaml.safe_load(path.read_text()) if path.exists() else {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
```

---

## Part 8: Migration Path

### Phase 1: Clean Up (Day 1)

1. Delete `indexer/` directory
2. Delete `container.py`
3. Delete `checkpoint.py`
4. Delete `streaming_sync.py`
5. Delete dead code (WorkspaceManager, EventBridge, snapshot stubs)
6. Flatten config.py

**Result**: Cleaner base to build on

### Phase 2: Extend EventStore (Day 1-2)

1. Add routing columns (`from_agent`, `to_agent`, `correlation_id`)
2. Add `get_inbox()` method
3. Add `AgentMessageEvent` to events.py

**Result**: Message bus ready

### Phase 3: Add Agent State (Day 2)

1. Create `agent_state.py` with `AgentState` class
2. Create `swarm_state.py` with `SwarmState` registry
3. Create `reconciler.py` for startup diff

**Result**: Persistent agents

### Phase 4: Add Agent Runner (Day 2-3)

1. Extract single-agent execution from `executor.py`
2. Create `agent_runner.py`
3. Integrate with agent state and EventStore

**Result**: Turn-based execution

### Phase 5: Add Neovim Server (Day 3-4)

1. Create `nvim/server.py`
2. Implement RPC handlers
3. Add to CLI

**Result**: Neovim integration

### Phase 6: Polish (Day 4-5)

1. Update CLI with swarm commands
2. Update HTTP API with swarm routes
3. Test end-to-end

**Result**: Unified system

---

## Part 9: What's Different From Original Analysis

### Changed Verdicts

| Component | Original Verdict | Revised Verdict | Reason |
|-----------|-----------------|-----------------|--------|
| EventStore | REMOVE | **KEEP & EXTEND** | It's the message bus! |
| EventBus | SIMPLIFY | **KEEP AS-IS** | Needed for live updates |
| Workspaces | KEEP | **KEEP & EXTEND** | Add state.jsonl |
| Context | SIMPLIFY | **MERGE** into agent state | Per-agent, not global |
| Executor | SIMPLIFY | **KEEP + EXTRACT** | AgentRunner for turns |

### Key Realization

The original analysis treated Remora as "just a batch executor" and tried to strip features. But with the swarm vision:

- **EventStore** isn't overhead, it's infrastructure
- **EventBus** isn't complexity, it's coordination
- **Workspaces** aren't just isolation, they're agent identity

We're not simplifying by removing - we're simplifying by **unifying the mental model**.

---

## Conclusion

### Before: Three Separate Concepts

1. Remora = batch graph execution
2. CST Swarm = persistent agent system (proposed)
3. Neovim = editor integration (proposed)

### After: One Unified System

> **Remora is a CST agent swarm where code constructs are persistent agents that communicate via an event store, with optional Neovim integration for visualization and interaction.**

### The Numbers

| Metric | Before | After |
|--------|--------|-------|
| Total LOC | ~4150 | ~3870 |
| Concepts to understand | 3 separate | 1 unified |
| Mental model complexity | High | Low |
| Capabilities | Less | More |

### The One-Liner

**Old**: "Remora runs agents in dependency order with isolated workspaces."

**New**: "Remora makes every function an agent you can talk to."

---

*Document version: 2.0*
*Status: Unified Analysis Complete*
