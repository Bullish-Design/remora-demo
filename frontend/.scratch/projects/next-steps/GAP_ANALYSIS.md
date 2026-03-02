# Remora Library Gap Analysis for Demo

**Date:** 2026-03-02
**Context:** The `EVENT_BASED_DEMO_PLAN.md` describes 22 tasks. Tasks T3-T13 involve modifications to the Remora library (`/home/andrew/Documents/Projects/remora/`). This document summarizes what's already done and what the library owner still needs to address.

---

## Executive Summary

**The library owner has already completed ~95% of the Option A migration.** T3-T11 and T13 are all implemented and working. The only substantive gap is in T12 (server.py wiring), and even that is a small issue. The demo can proceed with minimal library-side changes.

---

## Task-by-Task Audit

### DONE — No Action Needed

| Task | File(s) | Evidence |
|------|---------|----------|
| **T3**: `get_node_at_position()` | `core/event_store.py` | Method exists. 24 tests passing in `test_event_store_nodes_query.py` |
| **T4**: `set_node_status()` | `core/event_store.py` | Method exists with tests |
| **T5**: `remove_nodes_for_file()` | `core/event_store.py` | Method exists with tests |
| **T6**: Watcher returns dicts | `lsp/watcher.py` | `parse_and_inject_ids()` returns `list[dict]` with all required fields including `start_byte`/`end_byte` |
| **T7**: documents.py emits events | `lsp/handlers/documents.py` | Both `did_open` and `did_save` emit `NodeDiscoveredEvent`/`NodeRemovedEvent` to EventStore, handle orphan detection, update edges in RemoraDB |
| **T8**: LSP handlers use EventStore | `lsp/handlers/lens.py`, `hover.py`, `actions.py` | All read `AgentNode` from `server.event_store.list_nodes()` / `get_node_at_position()` / `get_recent_events()` |
| **T9**: commands.py uses EventStore | `lsp/handlers/commands.py` | All commands use `event_store.get_node_at_position()`, `get_node()`, `set_node_status()` |
| **T10**: runner.py uses EventStore | `lsp/runner.py` | Full execution loop uses EventStore. `execute_turn()` reads from EventStore, uses `AgentNode.to_system_prompt()`, `set_node_status()`, has full tool call loop with `rewrite_self`/`message_node`/`read_node`, cascade prevention, command queue polling |
| **T11**: notifications.py uses EventStore | `lsp/notifications.py` | `on_cursor_moved` uses `server.event_store.get_node_at_position()` |
| **T13**: LazyGraph reads from EventStore | `lsp/graph.py` | Dual-connection: edges from RemoraDB, nodes from EventStore. `_get_nodes_for_file()` and `_get_node()` read from EventStore's nodes table |

### RemoraDB — Confirmed Working

`lsp/db.py` (257 lines) has all required methods used by the already-migrated code:

| Method | Used By |
|--------|---------|
| `update_edges(nodes)` | `documents.py` (after node discovery) |
| `store_proposal(...)` | `runner.py` (after rewrite_self tool call) |
| `get_proposals_for_file(path)` | `commands.py` (for approve/reject) |
| `update_proposal_status(id, status)` | `commands.py` (approve/reject) |
| `get_proposal(id)` | `commands.py` |
| `update_cursor_focus(agent_id, path, line)` | `notifications.py` (cursor tracking) |
| `get_cursor_focus()` | Graph viewer reads this |
| `add_to_chain(correlation_id, agent_id)` | `runner.py` (cascade tracking) |
| `get_activation_chain(correlation_id)` | `runner.py` (cascade prevention) |
| `push_command(type, agent_id, payload)` | Graph viewer writes commands |
| `poll_commands(limit)` | `runner.py` background task |
| `mark_command_done(id)` | `runner.py` after dispatch |

The docstring confirms the architecture: *"Node state lives in EventStore (core). Event storage also lives in EventStore. This DB holds LSP-specific operational state that doesn't belong in the event-sourced core."*

---

## Gaps — Action Needed

### Gap 1: T12 — Module-Level Server Singleton (SMALL)

**File:** `lsp/server.py:106`

**Current state:**
```python
server = RemoraLanguageServer()  # line 106 — no EventStore, no runner
```

**Problem:** The module-level singleton creates `RemoraLanguageServer()` with `event_store=None`. The demo entry point needs to either:
1. Replace this singleton with one that has an EventStore, or
2. Set `server.event_store` after import (which already works — `__init__` accepts it as a param)

**The demo entry point can handle this** without library changes by doing:
```python
from remora.core.event_store import EventStore
from remora.lsp.server import server

# In INITIALIZED handler:
event_store = EventStore(db_path)
server.event_store = event_store
# server.graph already has es_db_path=None, may need re-init
```

**However, there's a subtle issue:** `server.graph = LazyGraph(self.db, event_store_db_path=es_db_path)` is set in `__init__` with `es_db_path=None` when `event_store=None`. If the demo sets `server.event_store` later, `server.graph` won't know about it.

**Recommended library fix:** Add a method to `RemoraLanguageServer`:
```python
def configure_event_store(self, event_store) -> None:
    """Set the EventStore after initialization (for demo entry points)."""
    self.event_store = event_store
    es_db_path = str(event_store._db_path) if event_store else None
    self.graph = LazyGraph(self.db, event_store_db_path=es_db_path)
```

**Effort:** ~15 minutes, 5 lines of code.

### Gap 2: MockLLM Selection (DEMO-SIDE, NOT LIBRARY)

The plan's Section 10, Change 1 describes a `setup_runner()` method in `server.py` that imports `MockLLMClient` from `remora_demo`. This is **NOT a library change** — the library shouldn't know about `remora_demo`. Instead, the demo entry point handles this:

```python
# remora_demo/__main__.py (demo-side code):
from remora_demo.mock_llm import MockLLMClient
llm = MockLLMClient()
runner = AgentRunner(server=server, llm=llm)
server.runner = runner
```

**No library action needed.** The library already accepts `runner` as a settable attribute (`server.runner: "AgentRunner | None" = None`).

### Gap 3: emit_event() Dual-Write (VERIFY ONLY)

**File:** `lsp/server.py:57-65`

The current `emit_event()` writes to EventStore if available:
```python
async def emit_event(self, event) -> Any:
    if not getattr(event, "timestamp", None):
        event.timestamp = time.time()
    if self.event_store:
        await self.event_store.append("swarm", event)
    self.protocol.notify("$/remora/event", event.model_dump())
    return event
```

The plan (Section 10, Change 2) shows a slightly different version that also calls `self.db.store_event(event)` for RemoraDB dual-write. The current code does NOT write to `self.db` — it only writes to EventStore.

**Question for owner:** Does the current code intentionally skip the RemoraDB events table? The graph viewer's `state.py` may need to read events from somewhere. If events only go to EventStore, the graph viewer needs to read from EventStore's events table instead of RemoraDB.

**If the graph viewer reads events from EventStore (which it should):** No change needed.
**If the graph viewer reads events from RemoraDB's events table:** Add `self.db.store_event(event)` back to `emit_event()`.

**Effort:** Either 0 or 1 line, depending on answer.

---

## Summary

| Gap | Severity | Owner | Effort |
|-----|----------|-------|--------|
| Gap 1: `configure_event_store()` method | Low — demo can work around it | Library | 15 min |
| Gap 2: MockLLM selection | N/A — demo-side | Demo | Already planned |
| Gap 3: emit_event dual-write | Low — need to verify graph viewer event source | Library or Demo | 0-1 line |

**Total library-side work needed: ~15-30 minutes.**

The Remora library is in excellent shape for the demo. The Option A migration is essentially complete.
