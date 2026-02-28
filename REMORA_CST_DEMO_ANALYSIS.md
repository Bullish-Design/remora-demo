# Remora CST Agent Swarm - Simplified Architecture

## Executive Summary

This document describes the architecture for a **CST Agent Swarm** - a system where every node in a codebase's Concrete Syntax Tree operates as an autonomous agent. The key insight is that this can be achieved with **minimal changes to existing Remora** by treating:

- **Agent = Workspace + persisted state**
- **Message bus = EventStore (already SQLite)**
- **Execution = turn-based, not continuous**
- **Overlay filesystems = Jujutsu VCS**

---

## Part 1: Core Concepts

### 1.1 The CST Agent Model

Every CST node becomes an agent with persistent state:

```
workspace/
├── swarm_state.db              ← SQLite: agent registry + metadata
├── events.db                   ← SQLite: EventStore (message bus)
├── agents/
│   ├── file_main_py/
│   │   ├── state.jsonl         ← agent identity, connections, chat history
│   │   └── workspace.db        ← Cairn workspace (CoW content)
│   ├── func_format_date/
│   │   ├── state.jsonl
│   │   └── workspace.db
│   └── class_user/
│       ├── state.jsonl
│       └── workspace.db
└── jj/                         ← Jujutsu repo (optional, for versioning)
```

### 1.2 Agent Capabilities

Each agent has:

| Capability | Implementation |
|------------|----------------|
| **Identity** | `state.jsonl` - id, name, node_type, path, parent_id |
| **Workspace** | `workspace.db` - Cairn CoW workspace (existing) |
| **Inbox** | EventStore query: `WHERE to_agent = ?` |
| **Outbox** | EventStore append with `from_agent` field |
| **Tools** | Existing Grail tools + messaging tools |
| **Memory** | `state.jsonl` - learned connections dict |
| **Content** | Workspace read/write (existing) |

### 1.3 Communication via EventStore

Messages are just events with routing fields:

```python
@dataclass(frozen=True)
class AgentMessageEvent:
    """A message between agents."""
    from_agent: str
    to_agent: str           # agent_id, "parent", "broadcast", or "find:symbol_name"
    action: str             # "request", "response", "notify"
    content: dict[str, Any]
    correlation_id: str | None = None  # for request/response pairing
    timestamp: float = field(default_factory=time.time)
```

Routing is simple:
- **Direct**: `to_agent = "func_format_date"` → query by agent_id
- **Parent**: `to_agent = "parent"` → resolve from agent's state.jsonl
- **Broadcast**: `to_agent = "broadcast:children"` → query all with matching parent_id
- **Find**: `to_agent = "find:User"` → propagate up tree until found

### 1.4 Turn-Based Execution

Agents are **dormant by default**. They activate on:

1. **File change** - file watcher detects modification
2. **Message received** - poll EventStore or subscribe
3. **User interaction** - direct chat via UI
4. **Scheduled** - periodic self-improvement cycles

When activated, an agent:
1. Loads state from `state.jsonl`
2. Reads inbox from EventStore
3. Runs one kernel turn (existing `AgentKernel`)
4. Writes outbox to EventStore
5. Saves state to `state.jsonl`
6. Goes dormant

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Lifecycle                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    trigger     ┌──────────┐    complete   ┌──────┐│
│  │ DORMANT │ ─────────────► │ RUNNING  │ ────────────► │ SAVE ││
│  └────┬────┘                └────┬─────┘               └──┬───┘│
│       │                          │                        │     │
│       │◄─────────────────────────┴────────────────────────┘     │
│       │                                                         │
│  Triggers:                   Actions:                           │
│  - File changed              - Load state.jsonl                 │
│  - Message in inbox          - Read inbox (EventStore)          │
│  - User chat                 - Run AgentKernel turn             │
│  - Scheduled tick            - Write outbox (EventStore)        │
│                              - Save state.jsonl                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.5 Startup: Diff Reconciliation

On startup:

1. **Discover** - Run tree-sitter on current files
2. **Load** - Read `swarm_state.db` for last known agents
3. **Diff** - Compare discovered nodes vs saved state
4. **Reconcile**:
   - New nodes → spawn agents
   - Deleted nodes → mark agents as orphaned
   - Changed nodes → queue update notification
5. **Restore** - Load each agent's `state.jsonl`
6. **Resume** - Process any pending inbox messages

```python
async def reconcile_on_startup(workspace_path: Path) -> SwarmState:
    # 1. Discover current CST
    current_nodes = discover(workspace_path)
    current_ids = {node.node_id for node in current_nodes}

    # 2. Load saved state
    saved_agents = await load_swarm_state(workspace_path / "swarm_state.db")
    saved_ids = set(saved_agents.keys())

    # 3. Diff
    new_ids = current_ids - saved_ids
    deleted_ids = saved_ids - current_ids
    existing_ids = current_ids & saved_ids

    # 4. Reconcile
    for node_id in new_ids:
        await spawn_agent(node_id, current_nodes[node_id])

    for node_id in deleted_ids:
        await mark_agent_orphaned(node_id)

    for node_id in existing_ids:
        if content_changed(current_nodes[node_id], saved_agents[node_id]):
            await queue_update_notification(node_id)

    return SwarmState(...)
```

### 1.6 Jujutsu for Overlay Filesystems

The key insight: **CST hierarchy maps to the same files**.

- A file agent and its function children all reference `main.py`
- No need for complex overlay - they're literally the same file
- Jujutsu tracks changes at the file level

One-way sync: Remora → Jujutsu (never reverse)

```bash
# After agent makes changes
jj status                    # See what changed
jj commit -m "Agent: func_format_date added timezone support"
```

Benefits:
- Full history of agent modifications
- Easy rollback if agent breaks something
- No merge conflicts (one-way sync)
- Human can review agent changes before accepting

---

## Part 2: Architecture

### 2.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CST Agent Swarm (Simplified)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                         Swarm Runtime                               │     │
│  │                                                                     │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │     │
│  │  │   Agent     │  │   Agent     │  │   Agent     │   (dormant)    │     │
│  │  │  (file)     │  │  (func)     │  │  (class)    │                │     │
│  │  │             │  │             │  │             │                │     │
│  │  │ state.jsonl │  │ state.jsonl │  │ state.jsonl │                │     │
│  │  │ workspace.db│  │ workspace.db│  │ workspace.db│                │     │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │     │
│  │         │                │                │                        │     │
│  │         └────────────────┼────────────────┘                        │     │
│  │                          │                                         │     │
│  │  ┌───────────────────────┴───────────────────────────────────┐    │     │
│  │  │                    EventStore (SQLite)                     │    │     │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │    │     │
│  │  │  │ events.db   │  │ Append      │  │ Query by        │   │    │     │
│  │  │  │             │  │ (emit)      │  │ to_agent/type   │   │    │     │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────┘   │    │     │
│  │  └────────────────────────────────────────────────────────────┘    │     │
│  │                                                                     │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                      Existing Remora (Unchanged)                    │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │     │
│  │  │ AgentKernel │  │ Grail Tools │  │ Discovery   │  │ EventBus │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘ │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                         External (Optional)                         │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐│     │
│  │  │ Jujutsu VCS │  │ File Watcher│  │ Neovim Plugin               ││     │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘│     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Details

#### SwarmState (New: ~100 lines)

```python
@dataclass
class SwarmState:
    """Global swarm state backed by SQLite."""
    db_path: Path
    agents: dict[str, AgentMetadata]  # agent_id -> metadata

    async def register_agent(self, agent_id: str, metadata: AgentMetadata) -> None:
        """Register a new agent."""

    async def get_agent(self, agent_id: str) -> AgentMetadata | None:
        """Get agent metadata."""

    async def list_agents(self, parent_id: str | None = None) -> list[AgentMetadata]:
        """List agents, optionally filtered by parent."""

    async def mark_orphaned(self, agent_id: str) -> None:
        """Mark an agent as orphaned (source node deleted)."""
```

#### AgentState (New: ~50 lines)

```python
@dataclass
class AgentState:
    """Per-agent state stored in state.jsonl."""
    identity: AgentIdentity
    connections: dict[str, str]   # symbolic_name -> agent_id
    chat_history: list[Message]
    last_content_hash: str
    last_activated: float

    @classmethod
    def load(cls, path: Path) -> "AgentState":
        """Load from JSONL file."""

    def save(self, path: Path) -> None:
        """Save to JSONL file (append-only for history)."""
```

#### EventStore Extension (Modify: ~50 lines)

Add routing columns to existing EventStore:

```sql
-- Add to existing events table
ALTER TABLE events ADD COLUMN from_agent TEXT;
ALTER TABLE events ADD COLUMN to_agent TEXT;
ALTER TABLE events ADD COLUMN correlation_id TEXT;

CREATE INDEX idx_events_to_agent ON events(to_agent);
CREATE INDEX idx_events_correlation ON events(correlation_id);
```

New query method:

```python
async def get_inbox(
    self,
    agent_id: str,
    *,
    since_id: int | None = None,
    include_broadcasts: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Get messages for an agent."""
    query = """
        SELECT * FROM events
        WHERE (to_agent = ? OR (to_agent = 'broadcast' AND ? = 'broadcast'))
    """
    if include_broadcasts:
        query += " OR to_agent LIKE 'broadcast:%'"
    if since_id:
        query += " AND id > ?"
    query += " ORDER BY id ASC"
    # ...
```

#### AgentRunner (New: ~150 lines)

Orchestrates single-agent execution:

```python
class AgentRunner:
    """Runs a single agent turn."""

    def __init__(
        self,
        config: RemoraConfig,
        event_store: EventStore,
        swarm_state: SwarmState,
    ):
        self.config = config
        self.event_store = event_store
        self.swarm_state = swarm_state

    async def run_turn(self, agent_id: str, trigger: TriggerEvent) -> TurnResult:
        """Run one turn for an agent."""
        # 1. Load state
        agent_state = AgentState.load(self._state_path(agent_id))
        workspace = await self._get_workspace(agent_id)

        # 2. Read inbox
        inbox = await self.event_store.get_inbox(
            agent_id,
            since_id=agent_state.last_seen_event_id
        )

        # 3. Build prompt with inbox messages
        prompt = self._build_prompt(agent_state, inbox, trigger)

        # 4. Run kernel (existing)
        kernel = self._create_kernel(agent_id, workspace)
        result = await kernel.run(messages=[
            Message(role="system", content=self._system_prompt(agent_state)),
            Message(role="user", content=prompt),
        ], tools=self._get_tools(agent_state))

        # 5. Process outgoing messages from tool calls
        for tool_call in result.tool_calls:
            if tool_call.name == "send_message":
                await self.event_store.append(
                    graph_id=self.swarm_state.swarm_id,
                    event=AgentMessageEvent(
                        from_agent=agent_id,
                        to_agent=tool_call.args["to"],
                        action=tool_call.args["action"],
                        content=tool_call.args["content"],
                    )
                )

        # 6. Save state
        agent_state.last_activated = time.time()
        agent_state.save(self._state_path(agent_id))

        return TurnResult(agent_id=agent_id, output=result.output)
```

#### SwarmScheduler (New: ~100 lines)

Decides which agents to run:

```python
class SwarmScheduler:
    """Schedules agent activations."""

    def __init__(
        self,
        swarm_state: SwarmState,
        event_store: EventStore,
        runner: AgentRunner,
    ):
        self.swarm_state = swarm_state
        self.event_store = event_store
        self.runner = runner
        self._file_watcher: FileWatcher | None = None

    async def start(self) -> None:
        """Start the scheduler."""
        # Watch for file changes
        self._file_watcher = FileWatcher(self._on_file_change)
        await self._file_watcher.start()

        # Subscribe to new messages
        self.event_store.subscribe(AgentMessageEvent, self._on_message)

    async def _on_file_change(self, path: Path) -> None:
        """Handle file change."""
        # Find agents affected by this file
        agents = await self.swarm_state.list_agents_for_file(path)
        for agent in agents:
            await self.runner.run_turn(
                agent.id,
                TriggerEvent(type="file_change", path=str(path))
            )

    async def _on_message(self, event: AgentMessageEvent) -> None:
        """Handle new message."""
        if event.to_agent.startswith("broadcast:"):
            # Resolve broadcast targets
            targets = await self._resolve_broadcast(event.to_agent)
        elif event.to_agent == "find":
            # Propagate find request
            targets = await self._propagate_find(event)
        else:
            targets = [event.to_agent]

        for target in targets:
            await self.runner.run_turn(
                target,
                TriggerEvent(type="message", message_id=event.id)
            )
```

### 2.3 New Tools for Messaging

Add to existing Grail tool registry:

```python
# tools/send_message.pym
"""Send a message to another agent."""

from Input import to_agent, action, content

# Validate
if to_agent not in ("parent", "broadcast:children", "broadcast:siblings"):
    # Check if it's a known connection
    if to_agent not in connections:
        # Must be a find request
        submit_result({
            "to_agent": f"find:{to_agent}",
            "action": action,
            "content": content,
        })
    else:
        submit_result({
            "to_agent": connections[to_agent],
            "action": action,
            "content": content,
        })
else:
    submit_result({
        "to_agent": to_agent,
        "action": action,
        "content": content,
    })
```

```python
# tools/request.pym
"""Send a request and wait for response."""

from Input import to_agent, action, params, timeout_turns

correlation_id = generate_correlation_id()

# Send request
send_message(
    to_agent=to_agent,
    action="request",
    content={"action": action, "params": params, "correlation_id": correlation_id}
)

# Response will arrive in next turn - agent must check inbox
submit_result({
    "correlation_id": correlation_id,
    "status": "pending",
})
```

---

## Part 3: File Structure

```
remora/
├── core/
│   ├── __init__.py
│   ├── agent.py              [KEEP] AgentKernel usage
│   ├── config.py             [KEEP]
│   ├── container.py          [KEEP]
│   ├── context.py            [KEEP]
│   ├── discovery.py          [KEEP]
│   ├── errors.py             [EXTEND] + SwarmError
│   ├── event_bus.py          [KEEP]
│   ├── event_store.py        [EXTEND] + routing columns, get_inbox()
│   ├── events.py             [EXTEND] + AgentMessageEvent
│   ├── executor.py           [KEEP] Used for single-agent runs
│   ├── graph.py              [KEEP]
│   ├── workspace.py          [KEEP] AgentWorkspace
│   └── tools/
│       ├── grail.py          [KEEP]
│       ├── send_message.py   [NEW]
│       └── request.py        [NEW]
│
├── swarm/                    [NEW] ~400 lines total
│   ├── __init__.py
│   ├── state.py              # SwarmState, AgentState
│   ├── runner.py             # AgentRunner
│   ├── scheduler.py          # SwarmScheduler
│   └── reconciler.py         # Startup diff reconciliation
│
├── service/
│   ├── api.py                [KEEP]
│   ├── swarm_api.py          [NEW] Swarm HTTP endpoints
│   └── handlers.py           [KEEP]
│
└── adapters/
    └── starlette.py          [EXTEND] + swarm routes
```

**Total new code: ~400 lines** (vs ~2000 in original proposal)

---

## Part 4: Implementation Plan

### Phase 1: EventStore Extension

1. Add `from_agent`, `to_agent`, `correlation_id` columns
2. Add `get_inbox()` query method
3. Add `AgentMessageEvent` to events.py

**Estimated: ~50 lines changed**

### Phase 2: Agent State Persistence

1. Create `AgentState` dataclass with JSONL serialization
2. Create `SwarmState` for agent registry
3. Integrate with existing workspace paths

**Estimated: ~150 lines new**

### Phase 3: Agent Runner

1. Create `AgentRunner` using existing `AgentKernel`
2. Add inbox processing to prompt building
3. Add outbox processing from tool calls

**Estimated: ~150 lines new**

### Phase 4: Scheduler & Reconciler

1. Create `SwarmScheduler` with file watcher
2. Create startup reconciler (discovery diff)
3. Wire up message subscription

**Estimated: ~150 lines new**

### Phase 5: HTTP API & Demo

1. Add swarm endpoints to Starlette adapter
2. Build simple demo UI
3. Test with sample codebase

**Estimated: ~100 lines new**

---

## Part 5: API Reference

### Swarm Service Endpoints

```
POST   /swarm/start
  Body: { path: string }
  Response: { swarm_id: string, agent_count: number }

POST   /swarm/stop
  Body: { swarm_id: string }
  Response: { success: boolean }

GET    /swarm/agents
  Query: ?parent_id=X&status=active
  Response: { agents: AgentSummary[] }

GET    /swarm/agents/{id}
  Response: { agent: AgentDetail, inbox: Message[], state: AgentState }

POST   /swarm/agents/{id}/chat
  Body: { message: string }
  Response: { response: string, tool_calls: ToolCall[] }

POST   /swarm/agents/{id}/trigger
  Body: { type: "file_change" | "manual" }
  Response: { turn_result: TurnResult }

GET    /swarm/events
  Query: ?since_id=X&agent_id=Y
  SSE stream of events
```

### Message Types

```python
@dataclass(frozen=True)
class AgentMessageEvent:
    from_agent: str
    to_agent: str
    action: str             # "request", "response", "notify"
    content: dict[str, Any]
    correlation_id: str | None = None
    timestamp: float = field(default_factory=time.time)

# Actions
action = "request"   # Expects response
action = "response"  # Reply to request
action = "notify"    # Fire-and-forget

# Special to_agent values
to_agent = "parent"              # Send to parent agent
to_agent = "broadcast:children"  # Send to all children
to_agent = "broadcast:siblings"  # Send to all siblings
to_agent = "find:symbol_name"    # Propagate up until found
```

---

## Part 6: Key Insights

### Why This Works

1. **Agent = Workspace + State**
   - No complex lifecycle management
   - State is just files (debuggable, portable)
   - Existing Cairn workspaces handle CoW

2. **EventStore = Message Bus**
   - Already SQLite with proper indexing
   - Just add routing columns
   - Replay support built-in

3. **Turn-Based = Simple**
   - No async coordination complexity
   - Agents run one at a time or in parallel batches
   - Easy to reason about, debug, checkpoint

4. **Jujutsu = Free Versioning**
   - One-way sync (Remora → jj)
   - Full history of agent changes
   - Human review before accepting

### Trade-offs

| Approach | Latency | Complexity | Debuggability |
|----------|---------|------------|---------------|
| Continuous async | Low | High | Hard |
| **Turn-based** | Medium | **Low** | **Easy** |
| Request-response | High | Medium | Medium |

For a code editing swarm, turn-based is ideal because:
- Code changes don't need millisecond latency
- File writes are naturally batched
- Human review is often desired anyway

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Agent** | Workspace + state representing a CST node |
| **Dormant** | Agent not currently executing (default state) |
| **Turn** | One activation cycle: load → process → save |
| **Inbox** | EventStore query for messages to this agent |
| **Outbox** | EventStore append of messages from this agent |
| **Reconciliation** | Startup diff between discovery and saved state |

---

*Document version: 2.0*
*Status: Simplified Architecture - Ready for Implementation*
