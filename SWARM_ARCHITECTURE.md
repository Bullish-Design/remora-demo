# Swarm vs. Event System: Do We Need The Swarm Layer?

**Verdict: No. The event system provides the essential architecture. The swarm layer adds complexity for a "every code element = agent" paradigm that can be achieved more simply.**

---

## Table of Contents

1. [The Two Layers](#1-the-two-layers)
2. [What The Event System Provides](#2-what-the-event-system-provides)
3. [What The Swarm Layer Adds](#3-what-the-swarm-layer-adds)
4. [Component-by-Component Analysis](#4-component-by-component-analysis)
5. [The Event System Can Replace The Swarm](#5-the-event-system-can-replace-the-swarm)
6. [What You'd Keep vs. Drop](#6-what-youd-keep-vs-drop)
7. [Architecture Without The Swarm](#7-architecture-without-the-swarm)
8. [Risks of Keeping The Swarm](#8-risks-of-keeping-the-swarm)

---

## 1. The Two Layers

The Remora codebase cleanly separates into two layers:

### Event System (~1,400 lines) — The Foundation

| Component | File | Lines | Role |
|-----------|------|-------|------|
| EventStore | `core/event_store.py` | 603 | Append-only SQLite event log with projections |
| EventBus | `core/event_bus.py` | 139 | In-process pub/sub for real-time UI updates |
| SubscriptionRegistry | `core/subscriptions.py` | 320 | Pattern-based routing: event_type, from/to agent, path glob, tags |
| NodeProjection | `core/projections.py` | 144 | Materializes events into queryable `nodes` table |
| Event Types | `core/events.py` | 227 | All event dataclasses (agent lifecycle, messaging, node discovery) |

### Swarm Layer (~2,800 lines) — The Question Mark

| Component | File | Lines | Role |
|-----------|------|-------|------|
| Discovery | `core/discovery.py` | 340 | Tree-sitter parsing to find every function/class/file |
| Reconciler | `core/reconciler.py` | 185 | Diff discovered nodes vs EventStore, emit events |
| AgentNode | `core/agent_node.py` | 279 | Unified model with LLM prompt gen + LSP helpers |
| SwarmExecutor | `core/swarm_executor.py` | 396 | LLM execution via structured-agents kernel |
| AgentRunner | `lsp/runner.py` | 819 | LLM execution + tool loop + cascade prevention |
| CairnWorkspaceService | `core/cairn_bridge.py` | 213 | Per-agent isolated Cairn workspaces |
| AgentWorkspace | `core/workspace.py` | 191 | Agent→stable→disk fallback reads |
| Swarm Tools | `core/tools/swarm.py` | 323 | 5 tools: send_message, subscribe, unsubscribe, broadcast, query_agents |
| Extensions | `extensions.py` | 125 | Config-driven agent specialization |

The event system is 2x smaller and provides the entire reactive infrastructure. The swarm layer consumes it.

---

## 2. What The Event System Provides

The event system alone gives you everything needed for a reactive, event-sourced application:

### Event Sourcing

Every state change is an appended event (`event_store.py:184-239`). The `append()` method:

1. Serializes the event to JSON
2. INSERTs into the `events` table with routing columns (`from_agent`, `to_agent`, `correlation_id`, `tags`)
3. Applies projections (e.g., `NodeProjection`) within the **same transaction**
4. Queries `SubscriptionRegistry.get_matching_agents()` for reactive triggers
5. Emits to `EventBus` for UI streaming

This is a complete event-sourcing pipeline in a single method call.

### Subscription-Based Routing

`SubscriptionPattern` (`subscriptions.py:27-74`) supports 5 filter dimensions:

- `event_types` — match by event class name (OR within list)
- `from_agents` — match by sender agent ID
- `to_agent` — match by recipient
- `path_glob` — match by file path pattern
- `tags` — match by arbitrary tags

All fields are optional (None = match anything). Fields combine with AND logic. This is expressive enough to route any event to any handler.

### Materialized State

`NodeProjection.apply()` (`projections.py:40-143`) updates the `nodes` table in the same transaction as the event INSERT. The `nodes` table has 21 columns including `status`, `source_hash`, `extension_name`, `custom_system_prompt`, `extra_tools`. This means:

- Current state is always queryable (no need to replay events)
- State is always consistent with the event log (same transaction)

### Real-Time Streaming

`EventBus` (`event_bus.py:25-133`) provides:

- Type-based `subscribe()` + wildcard `subscribe_all()`
- `stream()` context manager for async iteration
- `wait_for()` with predicate and timeout

This feeds the UI (via `UiStateProjector`) and SSE streams.

### Correlation Tracking

Events carry `correlation_id` for linking related events into chains. `get_events_for_correlation()` (`event_store.py:331-354`) retrieves the full chain. This provides conversation threading, causality tracking, and debugging.

**Bottom line: The event system is a complete reactive infrastructure. It handles persistence, routing, state materialization, real-time streaming, and correlation — all without any concept of "swarm."**

---

## 3. What The Swarm Layer Adds

The swarm layer builds on the event system to implement one specific idea: **every code element (function, class, file) is an autonomous LLM-powered agent**.

This idea requires:

1. **Automatic agent creation** — tree-sitter discovers code elements, reconciler emits `NodeDiscoveredEvent` for each
2. **Per-agent LLM execution** — each agent gets its own system prompt, context window, and tool set
3. **Agent-to-agent communication** — agents message each other via events, triggering cascading LLM calls
4. **Per-agent workspaces** — each agent gets an isolated Cairn workspace to prevent conflicts
5. **Cascade prevention** — depth limits, cooldowns, and cycle detection to prevent runaway chains

The question is: **Do you need the "every code element = agent" paradigm?** Or can you get the same results with events + a simpler execution model?

---

## 4. Component-by-Component Analysis

### Discovery (`discovery.py`) — REPLACEABLE

**What it does**: Uses tree-sitter to parse source files and extract `CSTNode` objects for every function, class, method, and file. `compute_node_id()` creates deterministic IDs via `sha256(file_path:name:start_line:end_line)[:16]` (`discovery.py:67-70`).

**What the event system needs instead**: Something to populate the `nodes` table. This could be:
- A simple file watcher that registers one agent per file (not per function)
- A manifest file listing the entities you care about
- Manual registration via CLI/API
- IDE integration that registers agents on demand

The tree-sitter discovery is sophisticated but only necessary if you want **function-level granularity** in your agents. For most use cases, file-level or manually-selected agents are sufficient.

### Reconciler (`reconciler.py`) — REPLACEABLE

**What it does**: On startup, diffs discovered CSTNodes against the `nodes` table. For new nodes: emits `NodeDiscoveredEvent` + registers default subscriptions. For deleted nodes: emits `NodeRemovedEvent` + unregisters. For changed nodes: re-emits `NodeDiscoveredEvent` + `ContentChangedEvent`.

**What the event system needs instead**: Any mechanism that emits `NodeDiscoveredEvent` when entities are created and `NodeRemovedEvent` when they're deleted. The reconciler is just one way to do that.

### AgentNode (`agent_node.py`) — SIMPLIFIABLE

**What it does**: A 279-line Pydantic model that serves as DB row, LLM prompt source, and LSP protocol response. Key method: `to_system_prompt()` (`agent_node.py:143-173`) generates prompts like:

```
You are an autonomous AI agent embodying a Python function: `calculate_total`
Node ID: abc123
Location: src/billing.py:42-67
```

**What the event system needs instead**: A simpler model. The `nodes` table already exists. You need a way to generate prompts from node data, but that can be a function rather than a 279-line model with LSP helpers.

### SwarmExecutor (`swarm_executor.py`) — REPLACEABLE

**What it does**: Runs a single LLM turn for an agent. The `run_agent()` method (`swarm_executor.py:92-257`):
1. Resolves a bundle path from config
2. Loads a structured-agents manifest
3. Initializes a Cairn workspace
4. Injects swarm externals (emit_event, register_subscription, broadcast, query_agents)
5. Loads files via CairnDataProvider
6. Builds chat history from EventStore
7. Builds a prompt with target code + trigger event + history
8. Discovers Grail tools
9. Runs the kernel

Steps 1-4 and 8-9 are swarm-specific. Steps 5-7 are generic "call an LLM with context" that any execution layer would need. The core LLM call (`_run_kernel()` at `swarm_executor.py:281-328`) is just creating an `AgentKernel` and calling `kernel.run()`.

**What the event system needs instead**: An event handler that, when triggered, calls an LLM with appropriate context. This could be ~50 lines of code instead of 396.

### AgentRunner (`lsp/runner.py`) — PARTIALLY REPLACEABLE

**What it does**: The 819-line runner handles both LSP and headless modes. It adds:

- Tool loop with MAX_TOOL_ROUNDS=5 (`runner.py:455-484`)
- 3 built-in tools: `rewrite_self`, `message_node`, `read_node` (`runner.py:732-785`)
- Cascade prevention: depth tracking (`runner.py:246-266`), cooldown (`runner.py:252-259`), DB-backed chain detection (`runner.py:374-384`)
- Proposal system for code rewrites (`runner.py:676-708`)

The cascade prevention exists **only because** agents can trigger other agents. Without agent-to-agent messaging, you don't need it. The proposal system is genuinely useful but could be implemented as an event handler.

### CairnWorkspaceService (`cairn_bridge.py`) — SIMPLIFIABLE

**What it does**: Creates a "stable" project-wide workspace + per-agent workspaces (`cairn_bridge.py:89-118`). Each agent workspace path: `.remora/<swarm_id>/agents/<id[:2]>/<id>/workspace.db`. This prevents agents from overwriting each other's file modifications.

**What the event system needs instead**: If you're not running hundreds of concurrent agents, a single shared workspace is fine. The isolation only matters for the swarm's many-agents-editing-simultaneously scenario.

### Swarm Tools (`tools/swarm.py`) — UNNECESSARY

**What they do**: 5 tools that are thin wrappers around event system operations:

- `SendMessageTool` (`swarm.py:33-91`): Creates an `AgentMessageEvent` and calls `emit_event()`. That's it.
- `SubscribeTool` (`swarm.py:94-155`): Calls `register_subscription()`.
- `UnsubscribeTool` (`swarm.py:158-204`): Calls `unregister()`.
- `BroadcastTool` (`swarm.py:207-257`): Loops over agents matching a pattern, emits `AgentMessageEvent` for each.
- `QueryAgentsTool` (`swarm.py:260-311`): Calls `event_store.list_nodes()`.

Every single one of these is a one-liner delegation to the event system. The tools exist to give LLM agents access to the event system. If you don't have LLM agents that need to self-organize, you don't need these tools.

### Extension System (`extensions.py`) — SIMPLIFIABLE

**What it does**: Loads Python classes from `.remora/models/`, matches them against agents by type/name/path, and injects custom prompts, tools, and subscriptions.

**What the event system needs instead**: A config file. The matching logic is ~60 lines. The injection is just setting fields on a model. This doesn't need a plugin system.

---

## 5. The Event System Can Replace The Swarm

Here's the key insight: **everything the swarm does flows through events anyway**.

When agent A messages agent B, it emits `AgentMessageEvent`. The subscription system routes it to B. B's handler runs an LLM turn. That's already the event system doing the work.

The swarm layer adds:
- **Who** to create agents for (discovery) — replaceable with simpler registration
- **How** to call the LLM (SwarmExecutor/AgentRunner) — replaceable with a thin handler
- **What** to put in the prompt (AgentNode.to_system_prompt) — replaceable with a function
- **Safety** for cascades (depth/cooldown/cycle) — unnecessary without swarm messaging

None of these are architecturally fundamental. They're application-layer concerns built on top of the event infrastructure.

### Proof: The Reactive Loop Without The Swarm

Today's flow:
```
Code change → file watcher → discovery → reconcile → NodeDiscoveredEvent
→ EventStore.append() → projection → SubscriptionRegistry.get_matching_agents()
→ trigger queue → AgentRunner.execute_turn() → LLM call → tool calls
→ rewrite_self → proposal → human approval → apply
```

Simplified flow (events only):
```
Code change → file watcher → ContentChangedEvent
→ EventStore.append() → SubscriptionRegistry.get_matching_agents()
→ trigger queue → simple_handler(agent_id, event) → LLM call
→ propose change → human approval → apply
```

The simplified flow skips: tree-sitter parsing, node-level reconciliation, AgentNode construction, Cairn workspace setup, cascade prevention. It still has: event sourcing, subscription routing, LLM execution, proposals.

---

## 6. What You'd Keep vs. Drop

| Keep (Event System) | Drop (Swarm Layer) | Replace With |
|---|---|---|
| `EventStore` | `discovery.py` (340 lines) | File-level registration or manual |
| `EventBus` | `reconciler.py` (185 lines) | Simple file watcher |
| `SubscriptionRegistry` | `swarm_executor.py` (396 lines) | ~50 line event handler |
| `NodeProjection` | `runner.py` cascade logic (200+ lines) | Not needed |
| `events.py` | `cairn_bridge.py` (213 lines) | Shared workspace |
| | `workspace.py` (191 lines) | Direct file reads |
| | `tools/swarm.py` (323 lines) | Not needed |
| | `extensions.py` (125 lines) | Config file |
| | `agent_node.py` LSP helpers (136 lines) | Simpler model |

**Lines kept**: ~1,400 (event system)
**Lines dropped**: ~2,100+ (swarm-specific)
**Lines replaced**: ~200 (simple handler + registration)

---

## 7. Architecture Without The Swarm

```
┌─────────────────────────────────────────────┐
│                  Events Layer                │
│                                              │
│  EventStore ─── NodeProjection ──► nodes DB  │
│      │                                       │
│      ├── SubscriptionRegistry                │
│      │      (routes events to handlers)      │
│      │                                       │
│      └── EventBus                            │
│            (streams to UI / SSE)             │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│            Thin Execution Layer              │
│                                              │
│  on_trigger(agent_id, event):                │
│    node = event_store.get_node(agent_id)     │
│    prompt = build_prompt(node, event)        │
│    response = await llm.chat(prompt)         │
│    if response.wants_edit:                   │
│      create_proposal(node, response.edit)    │
│                                              │
│  Registration:                               │
│    register_agent(file_path) →               │
│      NodeDiscoveredEvent + default subs      │
└─────────────────────────────────────────────┘
```

This gives you:
- Full event sourcing with replay and correlation
- Subscription-based routing
- Real-time UI streaming
- LLM execution on trigger
- Proposal-based code changes
- Human-in-the-loop approval

Without:
- Tree-sitter parsing of every function
- Per-function agent identities
- Agent-to-agent messaging cascades
- Per-agent workspace isolation
- Cascade prevention machinery

---

## 8. Risks of Keeping The Swarm

### Complexity Cost
The swarm layer is 2x the size of the event system. Every new feature must understand: discovery, reconciliation, agent identity, workspace isolation, cascade prevention, and two different execution paths (SwarmExecutor vs AgentRunner).

### Two Execution Paths
There are literally two different LLM execution implementations:
- `SwarmExecutor.run_agent()` (`swarm_executor.py:92-257`) — uses structured-agents kernel
- `AgentRunner.execute_turn()` (`runner.py:394-497`) — uses direct LLM client

Both do fundamentally the same thing (build prompt, call LLM, handle tools) but with different tool sets, different prompt builders, and different response handling. This is a maintenance burden.

### Cascade Risk
Agent-to-agent messaging creates the possibility of runaway cascading triggers. The system has 4 separate safety mechanisms (in-memory depth tracking, in-memory cooldown, DB-backed chain depth, DB-backed cycle detection) specifically to prevent this. These exist only because the swarm design creates the problem.

### Workspace Overhead
Each agent gets its own SQLite workspace database. For a project with 500 functions, that's 500 SQLite databases in `.remora/<swarm_id>/agents/`. The stable workspace must sync all project files on initialization (`cairn_bridge.py:139-172`). This is significant I/O overhead.

### Granularity Mismatch
The swarm treats every function as an equally capable agent. But not all code elements need LLM attention. A 3-line utility function doesn't benefit from having its own agent identity, workspace, and subscription set. The overhead is constant per agent regardless of whether the agent ever does anything useful.

---

## Summary

The event system (`EventStore` + `EventBus` + `SubscriptionRegistry` + `NodeProjection` + event types) is a solid, general-purpose reactive infrastructure. It provides everything needed for event sourcing, routing, state management, and real-time streaming.

The swarm layer builds a specific paradigm ("every code element = autonomous agent") on top of this infrastructure. That paradigm brings significant complexity (2,800+ lines, dual execution paths, cascade prevention, per-agent workspaces) for a benefit that can be achieved more simply: **trigger an LLM when something changes, propose edits, get human approval**.

**You don't need the swarm. The event system is the architecture. The swarm is one (complex) application of it.**
